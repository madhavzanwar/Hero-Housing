"""Connector contract for the external-data layer (PS2 point 1: "integrate data sources").

Every external source (credit bureau, NSDL PAN, UIDAI offline e-KYC, Account Aggregator, CERSAI,
UN sanctions list, GSTN/MCA, circle rates) is a :class:`Connector`. A connector receives one
:class:`FetchContext` and returns one :class:`~app.schemas.DataSourceResult`. :func:`run_connector`
wraps every call: it measures latency, stamps request references and converts any exception into a
``status="ERROR"`` result, so a broken source can never break the underwriting pipeline.

All sandbox connectors are deterministic (seeded from the case inputs) and return MASKED data only
(PAN ``XXXXX1234F``, Aadhaar last 4 digits) per DPDP Act 2023 / Aadhaar Act s.29.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from typing import Any, Literal, Protocol, runtime_checkable

from app.engine.masking import redact_text
from app.policy.loader import Policy
from app.schemas import ApplicationForm, BankAnalytics, DataSourceResult, DocType, DocumentBundle

Kind = Literal["BUREAU", "KYC", "BANKING", "REGISTRY", "SCREENING", "EMPLOYMENT", "PROPERTY"]
Mode = Literal["LIVE", "SANDBOX_MOCK", "OFFLINE_DATASET"]
Status = Literal["OK", "NO_MATCH", "HIT", "ERROR", "SKIPPED"]

#: fixed clock for deterministic payloads (as-of date of the demo data set)
AS_OF = date(2026, 11, 10)


@dataclass
class FetchContext:
    """Everything a connector may read. Built once per case by the hub."""
    form: ApplicationForm
    bundle: DocumentBundle
    policy: Policy
    case_ref: str
    consent_id: str
    bank: BankAnalytics | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------ helpers shared by connectors
    def seed(self, salt: str) -> int:
        """Deterministic integer seed derived from the case reference and a salt."""
        return int(hashlib.sha256(f"{self.case_ref}|{salt}".encode()).hexdigest()[:12], 16)

    def ref(self, prefix: str) -> str:
        return f"{prefix}-{self.seed(prefix) % 10**10:010d}"

    def doc_field(self, doc_type: DocType, name: str) -> Any:
        for d in self.bundle.documents:
            if d.doc_type == doc_type:
                v = d.field(name)
                if v not in (None, ""):
                    return v
        return None

    def cfg(self, key: str, default: Any = None) -> Any:
        return self.policy.get(f"integrations.{key}", default)


@runtime_checkable
class Connector(Protocol):
    id: str
    provider: str
    kind: Kind
    mode: Mode
    timeout_s: float

    def fetch(self, ctx: FetchContext) -> DataSourceResult: ...


def case_ref_for(form: ApplicationForm, bundle: DocumentBundle) -> str:
    """Stable case reference from the inputs (form + document hashes): same inputs -> same refs."""
    payload = form.model_dump_json(exclude={"bureau_score"}) + "|" + "|".join(
        sorted(d.sha256 or d.filename for d in bundle.documents))
    return "FP" + hashlib.sha256(payload.encode()).hexdigest()[:14].upper()


def consent_id_for(case_ref: str, purpose: str = "LOAN_UNDERWRITING") -> str:
    """Purpose-bound consent id (DPDP s.6 consent; AA / CICRA purpose limitation)."""
    h = hashlib.sha256(f"{case_ref}|{purpose}".encode()).hexdigest()
    return f"CNS-{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:28]}"


def result(conn: Connector, ctx: FetchContext, status: Status, summary: str, data: dict[str, Any],
           *, consent: bool = False, request_ref: str | None = None) -> DataSourceResult:
    return DataSourceResult(
        source=conn.id, provider=conn.provider, kind=conn.kind, status=status, mode=conn.mode,
        consent_id=ctx.consent_id if consent else None, request_ref=request_ref or ctx.ref(conn.id[:4]),
        summary=redact_text(summary), data=scrub(data), fetched_at=datetime.now(UTC))


_PAN_FULL = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_AADHAAR_FULL = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")


def scrub(obj: Any) -> Any:
    """Defence in depth: mask any full PAN / 12-digit Aadhaar pattern left in a payload's strings."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str) and (_PAN_FULL.search(obj) or _AADHAAR_FULL.search(obj)):
        return redact_text(obj)
    return obj


def run_connector(conn: Connector, ctx: FetchContext) -> DataSourceResult:
    """Call one connector, never raising: latency measured, exceptions -> status ERROR."""
    t0 = time.perf_counter()
    try:
        res = conn.fetch(ctx)
        if not isinstance(res, DataSourceResult):
            raise TypeError(f"connector returned {type(res).__name__}, expected DataSourceResult")
    except Exception as exc:
        res = DataSourceResult(
            source=getattr(conn, "id", "UNKNOWN"), provider=getattr(conn, "provider", "unknown"),
            kind=getattr(conn, "kind", "REGISTRY"), status="ERROR", mode=getattr(conn, "mode", "SANDBOX_MOCK"),
            request_ref=ctx.ref(str(getattr(conn, "id", "ERR"))[:4]),
            summary=f"Source unavailable: {type(exc).__name__}: {redact_text(str(exc))[:160]}",
            data={"error": type(exc).__name__}, fetched_at=datetime.now(UTC))
    res.latency_ms = max(res.latency_ms, int((time.perf_counter() - t0) * 1000))
    return res


def simulate_latency(ctx: FetchContext, conn_id: str) -> None:
    """Sleep a small deterministic 'network' latency (policy: integrations.simulated_latency_ms [lo, hi])."""
    lo, hi = ctx.cfg("simulated_latency_ms", [0, 0]) or [0, 0]
    if hi <= 0:
        return
    ms = int(lo) + ctx.seed("lat" + conn_id) % max(1, int(hi) - int(lo) + 1)
    time.sleep(ms / 1000.0)


# ------------------------------------------------------------------ name matching
_HONORIFICS = {"mr", "mrs", "ms", "dr", "shri", "smt", "kumari", "sri", "km"}


def name_tokens(name: str | None) -> list[str]:
    words = re.sub(r"[^a-z ]", " ", str(name or "").lower()).split()
    return [w for w in words if w not in _HONORIFICS]


def name_match_score(a: str | None, b: str | None) -> float:
    """0..100 name match robust to middle names, word order and OCR-merged words.

    max(token_set_ratio, ratio of the space-stripped sorted strings, ratio of space-stripped strings)."""
    from rapidfuzz import fuzz

    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    s1 = fuzz.token_set_ratio(" ".join(ta), " ".join(tb))
    s2 = fuzz.ratio("".join(ta), "".join(tb))
    s3 = fuzz.ratio("".join(sorted(ta)), "".join(sorted(tb)))
    return round(float(max(s1, s2, s3)), 1)


def seq_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
