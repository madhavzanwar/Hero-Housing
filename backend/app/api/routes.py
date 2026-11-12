"""REST API for FinPilot HomeLoan (mounted under ``/api``)."""
from __future__ import annotations

import contextlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field, ValidationError

from app.agent import audit as audit_log
from app.agent import qa
from app.agent.graph import status_for
from app.agent.llm import provider_status
from app.reports import memo
from app.schemas import (
    ApplicationForm,
    CaseDetail,
    CaseStatus,
    CaseSummary,
    CopilotAnswer,
    CopilotRequest,
    DecisionOutcome,
    Override,
    OverrideRequest,
    PortfolioMetrics,
    RuleCategory,
    RuleOutcome,
    Severity,
)
from app.store import get_store, guess_mime, list_personas, load_persona, safe_name, summarize

router = APIRouter(prefix="/api")
_STARTED = time.time()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
MARKDOWN = "text/markdown; charset=utf-8"


def demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "1").strip().lower() not in ("0", "false", "no", "off")


# --------------------------------------------------------------------------- response models
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    policy_version: str | None = None
    demo_mode: bool
    cases: int
    preload: dict[str, Any]
    llm: dict[str, Any]
    modules: dict[str, bool]
    uptime_s: float


class PersonaInfo(BaseModel):
    id: str
    applicant_name: str
    product: str
    employment_type: str
    city: str | None = None
    loan_amount: float
    property_value: float
    title: str | None = None
    segment: str | None = None
    description: str | None = None
    expected_outcomes: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    case_id: str | None = None


class PersonaDetail(PersonaInfo):
    form: ApplicationForm
    expected: dict[str, Any] = Field(default_factory=dict)


class AuditVerifyResponse(BaseModel):
    valid: bool
    events: int
    broken_at: int | None = None
    head: str | None = None


class DemoResetResponse(BaseModel):
    cases: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    ms: int


# --------------------------------------------------------------------------- helpers
def _case_or_404(case_id: str) -> CaseDetail:
    case = get_store().get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")
    return case


def _module_ok(mod: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _persona_info(p: Any) -> dict[str, Any]:
    f: ApplicationForm = p.form
    existing = get_store().by_persona(p.id)
    meta = p.raw if isinstance(p.raw, dict) else {}
    if isinstance(meta.get("persona"), dict):
        meta = {**meta, **meta["persona"]}
    exp = p.expected if isinstance(p.expected, dict) else {}
    return {
        "id": p.id, "applicant_name": f.applicant_name, "product": f.product.value,
        "employment_type": f.employment_type.value, "city": f.city or f.property_city,
        "loan_amount": f.loan_amount, "property_value": f.property_value,
        "title": meta.get("title") or meta.get("persona") or exp.get("title"),
        "segment": meta.get("segment"),
        "description": meta.get("story") or meta.get("description") or meta.get("summary") or exp.get("description")
        or exp.get("rationale") or exp.get("why"),
        "expected_outcomes": p.expected_outcomes, "files": p.files,
        "case_id": existing.id if existing else None,
    }


def _run_and_store(form: ApplicationForm, files: list[tuple[str, bytes]], persona_id: str | None = None) -> CaseDetail:
    from app.pipeline import run_case
    case = run_case(form, files, persona_id=persona_id)
    return get_store().put(case, files)


# --------------------------------------------------------------------------- system
@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    pv: str | None = None
    try:
        from app.policy.loader import get_policy
        pv = str(get_policy().version)
    except Exception:
        pv = None
    mods = {m: _module_ok(f"app.{m}") for m in (
        "documents.pipeline", "engine.eligibility", "engine.decision", "engine.fraud", "engine.compliance",
        "engine.bank", "capacity.forecast", "ml.scorer", "ml.features", "policy.loader")}
    st = get_store()
    return HealthResponse(version="1.0.0", policy_version=pv, demo_mode=demo_mode(), cases=len(st.all()),
                          preload=dict(st.preload), llm=provider_status(), modules=mods,
                          uptime_s=round(time.time() - _STARTED, 1))


@router.get("/policy", tags=["policy"])
def get_policy_doc() -> dict[str, Any]:
    """The machine-readable credit policy (thresholds, rule IDs, regulatory references)."""
    raw = memo.policy_raw()
    return {"version": raw.get("version"), "policy": raw, "rules": qa.policy_rule_index(raw)}


@router.get("/model-card", tags=["model"])
def model_card() -> dict[str, Any]:
    """Risk model metadata, metrics and fairness evaluation."""
    out: dict[str, Any] = {}
    try:
        from app.ml.scorer import model_info
        out.update(model_info())
    except ImportError:
        out["status"] = "ml module unavailable"
    art = Path(__file__).resolve().parents[1] / "ml" / "artifacts"
    for name in ("metrics.json", "model_card.json", "fairness.json"):
        fp = art / name
        if fp.is_file() and name.split(".")[0] not in out:
            with contextlib.suppress(ValueError):
                out[name.split(".")[0]] = json.loads(fp.read_text(encoding="utf-8"))
    return out


# --------------------------------------------------------------------------- personas
@router.get("/personas", response_model=list[PersonaInfo], tags=["personas"])
def personas() -> list[PersonaInfo]:
    return [PersonaInfo(**_persona_info(p)) for p in list_personas()]


@router.get("/personas/{persona_id}", response_model=PersonaDetail, tags=["personas"])
def persona(persona_id: str) -> PersonaDetail:
    p = load_persona(persona_id)
    if p is None:
        raise HTTPException(404, f"persona {persona_id} not found")
    return PersonaDetail(**_persona_info(p), form=p.form, expected=p.expected)


@router.get("/personas/{persona_id}/files/{filename}", tags=["personas"],
            response_class=FileResponse, responses={200: {"content": {"application/pdf": {}, "image/png": {}}}})
def persona_file(persona_id: str, filename: str) -> FileResponse:
    p = load_persona(persona_id)
    if p is None or safe_name(filename) not in p.files:
        raise HTTPException(404, "file not found")
    fp = p.path / safe_name(filename)
    return FileResponse(fp, media_type=guess_mime(fp.name), filename=fp.name,
                        content_disposition_type="inline")


# --------------------------------------------------------------------------- cases
@router.post("/cases", response_model=CaseDetail, tags=["cases"])
async def create_case(
    form: str = Form(..., description="ApplicationForm as a JSON string"),
    files: list[UploadFile] | None = File(None, description="Applicant documents (PDF/PNG/JPG)"),
    files_arr: list[UploadFile] | None = File(None, alias="files[]"),
) -> CaseDetail:
    """Underwrite a new application from uploaded documents."""
    try:
        app_form = ApplicationForm.model_validate_json(form)
    except ValidationError as exc:
        raise HTTPException(422, detail=json.loads(exc.json())) from exc
    uploads = list(files or []) + list(files_arr or [])
    payload: list[tuple[str, bytes]] = []
    for up in uploads:
        data = await up.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{up.filename} exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        payload.append((safe_name(up.filename or f"doc{len(payload) + 1}"), data))
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_run_and_store, app_form, payload)


@router.post("/cases/from-persona/{persona_id}", response_model=CaseDetail, tags=["cases"])
def create_case_from_persona(persona_id: str) -> CaseDetail:
    """Underwrite a fresh case from a synthetic persona's application + documents."""
    p = load_persona(persona_id)
    if p is None:
        raise HTTPException(404, f"persona {persona_id} not found")
    return _run_and_store(p.form, p.read_files(), persona_id=p.id)


@router.get("/cases", response_model=list[CaseSummary], tags=["cases"])
def list_cases() -> list[CaseSummary]:
    return get_store().summaries()


@router.get("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: str) -> CaseDetail:
    return _case_or_404(case_id)


@router.get("/cases/{case_id}/documents/{doc_id}", tags=["cases"], response_class=Response,
            responses={200: {"content": {"application/pdf": {}, "image/png": {}}}})
def get_document(case_id: str, doc_id: str) -> Response:
    _case_or_404(case_id)
    sf = get_store().document(case_id, doc_id)
    if sf is None or not sf.path.is_file():
        raise HTTPException(404, "document not found")
    return FileResponse(sf.path, media_type=sf.mime_type, filename=sf.filename, content_disposition_type="inline")


@router.get("/cases/{case_id}/audit/verify", response_model=AuditVerifyResponse, tags=["cases"])
def verify_audit(case_id: str) -> AuditVerifyResponse:
    """Recompute the sha256 hash chain of the case's audit trail."""
    return AuditVerifyResponse(**audit_log.verify(_case_or_404(case_id).audit))


@router.post("/cases/{case_id}/override", response_model=CaseDetail, tags=["underwriter"])
def override_case(case_id: str, req: OverrideRequest) -> CaseDetail:
    """Human-in-the-loop override: records who, what, why; keeps the engine's outcome for audit."""
    from app.engine.finance import emi as calc_emi
    case = _case_or_404(case_id).model_copy(deep=True)
    if not req.reason.strip() or len(req.reason.strip()) < 5:
        raise HTTPException(422, "a reason (min 5 characters) is required for an override")
    if not req.underwriter.strip():
        raise HTTPException(422, "underwriter name is required")
    d = case.decision
    from_outcome = d.outcome
    now = datetime.now(timezone.utc)
    approved = req.to_outcome in (DecisionOutcome.APPROVE, DecisionOutcome.APPROVE_WITH_CONDITIONS)
    if approved:
        amount = (req.sanctioned_amount or d.sanctioned_amount
                  or min(case.eligibility.requested_amount, case.eligibility.max_eligible_loan)
                  or case.eligibility.requested_amount)
        d.sanctioned_amount = float(amount)
        d.tenure_months = d.tenure_months or case.form.tenure_months
        d.rate = d.rate or case.eligibility.rate
        d.emi = round(float(calc_emi(d.sanctioned_amount, d.rate, d.tenure_months)), 2)
    elif req.to_outcome == DecisionOutcome.DECLINE:
        d.sanctioned_amount, d.emi = 0.0, 0.0
    ov = Override(at=now, underwriter=req.underwriter.strip(), from_outcome=from_outcome,
                  to_outcome=req.to_outcome, reason=req.reason.strip(),
                  sanctioned_amount=d.sanctioned_amount if approved else None)
    case.overrides.append(ov)
    d.outcome = req.to_outcome
    d.decided_by = req.underwriter.strip()
    d.decided_at = now
    case.status = CaseStatus.OVERRIDDEN
    audit_log.append(case.audit, f"underwriter:{ov.underwriter}", "OVERRIDE",
                     f"{from_outcome.value} → {req.to_outcome.value}: {ov.reason}",
                     {"from": from_outcome.value, "to": req.to_outcome.value,
                      "engine_outcome": d.engine_outcome.value, "sanctioned_amount": ov.sanctioned_amount,
                      "reason": ov.reason}, at=now)
    case.memo_markdown = memo.credit_memo(case)
    get_store().save(case)
    return case


@router.post("/cases/{case_id}/copilot", response_model=CopilotAnswer, tags=["copilot"])
def copilot(case_id: str, req: CopilotRequest) -> CopilotAnswer:
    """Ask the Underwriting Copilot a question; answers are grounded in this case + policy only."""
    case = _case_or_404(case_id)
    q = req.question.strip()
    if not q:
        raise HTTPException(422, "question is required")
    ans = qa.answer(case, q[:1000])
    audit_log.append(case.audit, "copilot", "COPILOT_QA", q[:200],
                     {"engine": ans.engine, "citations": [c.ref for c in ans.citations][:20]})
    get_store().save(case)
    return ans


@router.get("/cases/{case_id}/memo", response_class=PlainTextResponse, tags=["reports"],
            responses={200: {"content": {"text/markdown": {}}}})
def get_memo(case_id: str) -> PlainTextResponse:
    case = _case_or_404(case_id)
    return PlainTextResponse(case.memo_markdown or memo.credit_memo(case), media_type=MARKDOWN)


@router.get("/cases/{case_id}/sanction-letter", response_class=PlainTextResponse, tags=["reports"],
            responses={200: {"content": {"text/markdown": {}}}})
def get_sanction_letter(case_id: str) -> PlainTextResponse:
    """Sanction letter + KFS (approved), letter of regret with written reasons (declined), or referral note."""
    return PlainTextResponse(memo.outcome_letter(_case_or_404(case_id)), media_type=MARKDOWN)


@router.get("/cases/{case_id}/kfs", tags=["reports"])
def get_kfs(case_id: str) -> dict[str, Any]:
    """Key Facts Statement numbers (amount, ROI, EMI, fee, APR approximation, validity)."""
    return memo.kfs(_case_or_404(case_id))


# --------------------------------------------------------------------------- portfolio
def portfolio_metrics(cases: list[CaseDetail]) -> PortfolioMetrics:
    n = len(cases)
    by_outcome = Counter(c.decision.outcome.value for c in cases)
    by_product = Counter(c.form.product.value for c in cases)
    approved = [c for c in cases if c.decision.outcome in memo.APPROVED]

    def fraud(c: CaseDetail) -> bool:
        return any(r.category == RuleCategory.FRAUD and r.outcome == RuleOutcome.FAIL for r in c.decision.rules_fired) \
            or any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in c.bundle.flags)

    rule_counts: Counter[str] = Counter()
    names: dict[str, tuple[str, str]] = {}
    for c in cases:
        for r in c.decision.rules_fired:
            if r.outcome in (RuleOutcome.FAIL, RuleOutcome.WARN):
                rule_counts[r.rule_id] += 1
                names[r.rule_id] = (r.name, r.category.value)
    return PortfolioMetrics(
        total_cases=n,
        by_outcome={o.value: by_outcome.get(o.value, 0) for o in DecisionOutcome},
        by_product=dict(by_product),
        approval_rate=round(len(approved) / n, 4) if n else 0.0,
        avg_turnaround_ms=round(sum(c.decision.turnaround_ms for c in cases) / n, 1) if n else 0.0,
        fraud_flagged=sum(1 for c in cases if fraud(c)),
        avg_pd=round(sum(c.risk.pd for c in cases) / n, 4) if n else 0.0,
        sanctioned_value=round(sum(c.decision.sanctioned_amount for c in approved), 2),
        override_rate=round(sum(1 for c in cases if c.overrides) / n, 4) if n else 0.0,
        grade_distribution={g: sum(1 for c in cases if c.risk.grade == g) for g in "ABCDE"},
        top_rules=[{"rule_id": rid, "name": names[rid][0], "category": names[rid][1], "count": k}
                   for rid, k in rule_counts.most_common(10)],
    )


@router.get("/portfolio", response_model=PortfolioMetrics, tags=["portfolio"])
def portfolio() -> PortfolioMetrics:
    return portfolio_metrics(get_store().all())


# --------------------------------------------------------------------------- demo
@router.post("/demo/reset", response_model=DemoResetResponse, tags=["demo"])
def demo_reset() -> DemoResetResponse:
    """Clear all cases and re-underwrite every synthetic persona (DEMO_MODE only)."""
    if not demo_mode():
        raise HTTPException(403, "demo mode is disabled (set DEMO_MODE=1)")
    st = get_store()
    st.wait_preload()
    t = time.perf_counter()
    st.clear()
    res = st.preload_personas(force=True)
    return DemoResetResponse(cases=len(st.all()), errors=res.get("errors", []),
                             ms=int((time.perf_counter() - t) * 1000))


__all__ = ["portfolio_metrics", "router", "status_for", "summarize"]
