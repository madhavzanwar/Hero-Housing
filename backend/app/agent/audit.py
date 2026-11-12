"""Tamper-evident audit trail: each event's hash = sha256(prev_hash + canonical event JSON)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.schemas import AuditEvent

GENESIS = "0" * 64


def _canonical(ev: AuditEvent) -> str:
    payload = ev.model_dump(mode="json", exclude={"hash"})
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, ev: AuditEvent) -> str:
    return hashlib.sha256((prev_hash + _canonical(ev)).encode("utf-8")).hexdigest()


def append(audit: list[AuditEvent], actor: str, action: str, detail: str,
           data: dict[str, Any] | None = None, at: datetime | None = None) -> AuditEvent:
    """Append a new hash-chained event to ``audit`` (in place) and return it."""
    ev = AuditEvent(at=at or datetime.now(timezone.utc), actor=actor, action=action,
                    detail=detail, data=data or {})
    prev = audit[-1].hash if audit else GENESIS
    ev.hash = compute_hash(prev, ev)
    audit.append(ev)
    return ev


def verify(audit: list[AuditEvent]) -> dict[str, Any]:
    """Recompute the chain; returns ``{"valid": bool, "events": n, "broken_at": idx|None}``."""
    prev = GENESIS
    for i, ev in enumerate(audit):
        if compute_hash(prev, ev) != ev.hash:
            return {"valid": False, "events": len(audit), "broken_at": i}
        prev = ev.hash
    return {"valid": True, "events": len(audit), "broken_at": None, "head": prev}
