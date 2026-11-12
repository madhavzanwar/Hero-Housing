"""Shared helpers for the API / agent tests (imported by test_api_*.py and test_agent_graph.py)."""
from __future__ import annotations

import importlib.util
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("COPILOT_LLM", "none")
os.environ.setdefault("PRELOAD_PERSONAS", "0")
os.environ.setdefault("DEMO_MODE", "1")

PIPELINE_MODULES = [
    "app.documents.pipeline", "app.engine.bank", "app.engine.eligibility", "app.engine.fraud",
    "app.engine.compliance", "app.engine.decision", "app.engine.pricing", "app.capacity.forecast",
    "app.ml.features", "app.ml.scorer", "app.policy.loader",
]


def missing_modules() -> list[str]:
    out = []
    for m in PIPELINE_MODULES:
        try:
            if importlib.util.find_spec(m) is None:
                out.append(m)
        except ModuleNotFoundError:
            out.append(m)
    return out


def require_pipeline() -> None:
    miss = missing_modules()
    if miss:
        pytest.skip(f"pipeline modules not present yet: {miss}")


def require_personas() -> list[Any]:
    from app.store import list_personas
    ps = list_personas()
    if not ps:
        pytest.skip("no personas under data/personas yet")
    return ps


@lru_cache(maxsize=1)
def client() -> Any:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import reset_store
    reset_store(Path(tempfile.mkdtemp(prefix="finpilot-test-")))
    return TestClient(app)


_case_cache: dict[str, dict[str, Any]] = {}


def persona_case(pid: str) -> dict[str, Any]:
    """Run (once per session) a persona through POST /api/cases/from-persona and return the JSON."""
    if pid not in _case_cache:
        r = client().post(f"/api/cases/from-persona/{pid}")
        assert r.status_code == 200, r.text
        _case_cache[pid] = r.json()
    return _case_cache[pid]


def pick_persona(predicate: Any) -> str:
    for p in require_personas():
        if predicate(p):
            return str(p.id)
    pytest.skip("no persona matches")
    return ""


def fake_case() -> Any:
    """A hand-built CaseDetail (no engine needed) for unit tests of qa / memo / audit."""
    from datetime import datetime, timezone

    from app.agent import audit as audit_log
    from app.schemas import (
        ApplicantProfile,
        ApplicationForm,
        BankAnalytics,
        CaseDetail,
        CaseStatus,
        Condition,
        Decision,
        DecisionOutcome,
        DocumentBundle,
        Eligibility,
        RepaymentCapacity,
        RiskScore,
        RuleCategory,
        RuleHit,
        RuleOutcome,
        ShapReason,
    )
    now = datetime.now(timezone.utc)
    form = ApplicationForm(applicant_name="Test Applicant", declared_monthly_income=100000, existing_emi=20000,
                           loan_amount=4500000, property_value=6000000, tenure_months=240, bureau_score=760)
    hits = [
        RuleHit(rule_id="ELG-FOIR-02", name="FOIR within cap", category=RuleCategory.ELIGIBILITY,
                outcome=RuleOutcome.FAIL, detail="FOIR 61.0% exceeds cap 55%", effect="CONDITION",
                severity=__import__("app.schemas", fromlist=["Severity"]).Severity.MEDIUM),
        RuleHit(rule_id="LTV-HL-02", name="LTV within RBI slab", category=RuleCategory.ELIGIBILITY,
                outcome=RuleOutcome.PASS, detail="LTV 75.0% within 80%"),
    ]
    elig = Eligibility(policy_version="2026.11-v1", assessed_income=100000, income_basis="min(declared, slips, bank)",
                       existing_obligations=20000, foir_cap=0.55, foir_actual=0.61, ltv_cap=0.80, ltv_actual=0.75,
                       ltv_rule_id="LTV-HL-02", rate=0.086, max_tenure_months=300, age_at_maturity=52,
                       max_emi_affordable=35000, max_loan_by_foir=4000000, max_loan_by_ltv=4800000,
                       max_eligible_loan=4000000, requested_amount=4500000, requested_emi=39340, eligible=False)
    dec = Decision(outcome=DecisionOutcome.APPROVE_WITH_CONDITIONS, engine_outcome=DecisionOutcome.APPROVE_WITH_CONDITIONS,
                   model_suggested=DecisionOutcome.APPROVE, sanctioned_amount=4000000, tenure_months=240, rate=0.086,
                   emi=34970, reasons=["FOIR 61.0% exceeds the 55% cap; loan reduced to ₹40.00 L"],
                   conditions=[Condition(code="REDUCE_AMOUNT", text="Reduce loan amount to ₹40,00,000")],
                   rules_fired=hits, decided_at=now, policy_version="2026.11-v1", turnaround_ms=1200)
    case = CaseDetail(
        id="TEST-1", created_at=now, status=CaseStatus.DECIDED, form=form,
        applicant=ApplicantProfile(name="Test Applicant", employment_type=form.employment_type, pan_masked="XXXXX1234F"),
        bundle=DocumentBundle(), bank=BankAnalytics(months_covered=6, bounces=1, avg_monthly_balance=80000),
        eligibility=elig,
        risk=RiskScore(pd=0.03, score=740, grade="B", band="Moderate", model_version="test",
                       reasons=[ShapReason(feature="foir", label="FOIR", value="61%", impact=0.4,
                                           text="High FOIR raises risk")]),
        capacity=RepaymentCapacity(health_score=68, monthly_surplus_after_emi=15000, prob_shortfall=0.08,
                                   stress_emi_coverage=1.3),
        decision=dec,
    )
    audit_log.append(case.audit, "system", "CASE_CREATED", "test")
    audit_log.append(case.audit, "system", "DECISION", "test decision")
    return case
