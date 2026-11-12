"""Helper to build RuleHit objects from the policy rule catalogue."""
from __future__ import annotations

from typing import Any

from app.policy.loader import Policy
from app.schemas import RuleCategory, RuleHit, RuleOutcome, Severity


def hit(
    policy: Policy,
    rule_id: str,
    outcome: RuleOutcome,
    detail: str,
    *,
    effect: str = "NONE",
    severity: Severity = Severity.INFO,
    evidence: dict[str, Any] | None = None,
    name: str | None = None,
    category: RuleCategory | None = None,
    reference: str | None = None,
) -> RuleHit:
    meta = policy.rule(rule_id)
    cat = category or RuleCategory(meta.get("category", "RISK"))
    return RuleHit(
        rule_id=rule_id,
        name=name or str(meta.get("name", rule_id)),
        category=cat,
        outcome=outcome,
        detail=detail,
        effect=effect,  # type: ignore[arg-type]
        severity=severity,
        reference=reference if reference is not None else (policy.rule_reference(rule_id) or None),
        evidence=evidence or {},
    )
