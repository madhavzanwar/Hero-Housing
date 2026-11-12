""""Underwriting Copilot" — LangGraph StateGraph that orchestrates one case end to end.

intake → documents → missing_docs_check → bank_analytics → eligibility → fraud_compliance
       → risk_model → capacity → decision → credit_memo → audit

Every node is wrapped so that it appends ``{node, ms, summary}`` to the copilot trace and a
hash-chained :class:`~app.schemas.AuditEvent` to the audit trail. Engine / document / ML
modules are imported lazily inside nodes so that this module imports cleanly on its own.
"""
from __future__ import annotations

import itertools
import re
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent import audit as audit_log
from app.schemas import (
    ApplicantProfile,
    ApplicationForm,
    AuditEvent,
    BankAnalytics,
    CaseDetail,
    CaseStatus,
    Decision,
    DecisionOutcome,
    DocumentBundle,
    Eligibility,
    RepaymentCapacity,
    RiskScore,
    RuleHit,
    RuleOutcome,
)

NODE_ORDER = [
    "intake", "documents", "missing_docs_check", "bank_analytics", "eligibility",
    "fraud_compliance", "risk_model", "capacity", "decision", "credit_memo", "audit",
]

_NODE_ACTIONS = {
    "intake": "CASE_CREATED",
    "documents": "DOCUMENTS_PROCESSED",
    "missing_docs_check": "MISSING_DOCS_CHECK",
    "bank_analytics": "BANK_ANALYSED",
    "eligibility": "ELIGIBILITY_ASSESSED",
    "fraud_compliance": "FRAUD_COMPLIANCE_CHECKED",
    "risk_model": "MODEL_SCORED",
    "capacity": "CAPACITY_ASSESSED",
    "decision": "DECISION",
    "credit_memo": "MEMO_GENERATED",
    "audit": "CASE_FINALISED",
}

_NODE_ACTORS = {"risk_model": "ml-model", "credit_memo": "copilot", "audit": "copilot"}


class CopilotState(TypedDict, total=False):
    case_id: str
    persona_id: str | None
    started_at: datetime
    t0: float
    form: ApplicationForm
    files: list[tuple[str, bytes]]
    policy: Any
    bundle: DocumentBundle
    bank: BankAnalytics
    eligibility: Eligibility
    eligibility_hits: list[RuleHit]
    fraud_hits: list[RuleHit]
    compliance_hits: list[RuleHit]
    risk: RiskScore
    features: dict[str, float]
    capacity: RepaymentCapacity
    decision: Decision
    case: CaseDetail
    messages: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    audit: list[AuditEvent]


NodeFn = Callable[[CopilotState], tuple[dict[str, Any], str, dict[str, Any]]]

_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
_AADHAAR_RE = re.compile(r"^\d{12}$")


# --------------------------------------------------------------------------- helpers
def _policy() -> Any:
    from app.policy.loader import get_policy
    return get_policy()


def _rate(form: ApplicationForm, grade: str, policy: Any) -> float:
    from app.engine.pricing import rate_for
    return float(rate_for(form, grade, policy))


def _safe_pan(v: Any) -> str | None:
    if not v:
        return None
    s = str(v).strip().upper()
    if _PAN_RE.match(s):
        from app.engine.masking import mask_pan
        return str(mask_pan(s))
    return s


def _safe_aadhaar(v: Any) -> str | None:
    if not v:
        return None
    s = re.sub(r"\s", "", str(v))
    if _AADHAAR_RE.match(s):
        from app.engine.masking import mask_aadhaar
        return str(mask_aadhaar(s))
    return str(v)


def _age(dob: date | None) -> float:
    if not dob:
        return 0.0
    try:
        from app.engine.finance import age_on
        return round(float(age_on(dob, date.today())), 1)
    except ImportError:  # pragma: no cover - engine always present in prod
        return round((date.today() - dob).days / 365.25, 1)


def build_applicant(form: ApplicationForm, bundle: DocumentBundle) -> ApplicantProfile:
    ident = bundle.identity or {}
    dob_val = form.dob or ident.get("dob")
    dob: date | None = None
    if isinstance(dob_val, date):
        dob = dob_val
    elif isinstance(dob_val, str):
        try:
            dob = date.fromisoformat(dob_val[:10])
        except ValueError:
            dob = None
    return ApplicantProfile(
        name=form.applicant_name or str(ident.get("name", "")),
        dob=dob, age=_age(dob), gender=form.gender,
        pan_masked=_safe_pan(ident.get("pan_masked")),
        aadhaar_masked=_safe_aadhaar(ident.get("aadhaar_masked")),
        address=ident.get("address"), city=form.city or form.property_city,
        employment_type=form.employment_type, employer_or_business=form.employer_or_business,
    )


def _non_pass(hits: list[RuleHit]) -> list[RuleHit]:
    return [h for h in hits if h.outcome != RuleOutcome.PASS]


def all_rule_hits(state: CopilotState) -> list[RuleHit]:
    return (list(state.get("eligibility_hits", [])) + list(state.get("fraud_hits", []))
            + list(state.get("compliance_hits", [])))


def status_for(decision: Decision, bundle: DocumentBundle) -> CaseStatus:
    if decision.outcome == DecisionOutcome.REFER:
        return CaseStatus.IN_REVIEW
    if bundle.missing_documents and decision.outcome != DecisionOutcome.DECLINE:
        return CaseStatus.AWAITING_DOCUMENTS
    return CaseStatus.DECIDED


def _fmt_inr(x: float) -> str:
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


# --------------------------------------------------------------------------- nodes
# Each returns (state_update, one-line summary, audit data)
def node_intake(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    form = s["form"]
    policy = _policy()
    summary = (f"{form.product.value} {_fmt_inr(form.loan_amount)} on property "
               f"{_fmt_inr(form.property_value)}; {form.employment_type.value.lower()} applicant; "
               f"{len(s.get('files', []))} document(s) received; policy {policy.version}")
    return ({"policy": policy}, summary,
            {"product": form.product.value, "loan_amount": form.loan_amount,
             "property_value": form.property_value, "files": [f for f, _ in s.get("files", [])],
             "persona_id": s.get("persona_id"), "policy_version": policy.version})


def node_documents(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.documents.pipeline import process_documents
    bundle = process_documents(list(s.get("files", [])), s["form"])
    audit = s["audit"]
    for d in bundle.documents:
        audit_log.append(audit, "system", "DOCUMENT_INGESTED",
                         f"{d.filename} classified as {d.doc_type.value} via {d.ocr_engine}",
                         {"document_id": d.id, "doc_type": d.doc_type.value, "sha256": d.sha256,
                          "flags": [f.code for f in d.flags]})
    types = sorted({d.doc_type.value for d in bundle.documents})
    summary = (f"{len(bundle.documents)} documents read ({', '.join(types) or 'none'}); "
               f"{len(bundle.transactions)} bank transactions; {len(bundle.flags)} document flag(s)")
    return ({"bundle": bundle}, summary,
            {"documents": len(bundle.documents), "flags": [f.code for f in bundle.flags],
             "cross_checks_failed": [c.field for c in bundle.cross_checks if not c.match]})


def node_missing_docs(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    missing = [m.value for m in s["bundle"].missing_documents]
    messages = list(s.get("messages", []))
    if missing:
        text = ("Request for documents: please upload " + ", ".join(missing)
                + ". Assessment continues with the documents received; the decision will carry a "
                  "SUBMIT_DOC condition until these are provided.")
        messages.append({"type": "REQUEST_FOR_DOCUMENTS", "to": "RM / applicant",
                         "documents": missing, "text": text})
        audit_log.append(s["audit"], "copilot", "DOCUMENTS_REQUESTED", text, {"documents": missing})
        summary = f"Missing: {', '.join(missing)} — request-for-documents raised; continuing"
    else:
        summary = "All required documents present"
    return ({"messages": messages}, summary, {"missing": missing})


def node_bank(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.engine.bank import analyze
    bank = analyze(s["bundle"].transactions, s["policy"], employer=s["form"].employer_or_business)
    summary = (f"{bank.months_covered:.0f} months; AMB {_fmt_inr(bank.avg_monthly_balance)}; "
               f"income est. {_fmt_inr(bank.income_estimate)}/m; {bank.bounces} bounce(s); "
               f"{len(bank.detected_emis)} existing EMI(s) detected")
    return ({"bank": bank}, summary,
            {"months": bank.months_covered, "bounces": bank.bounces,
             "income_estimate": bank.income_estimate, "total_detected_emi": bank.total_detected_emi})


def node_eligibility(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.engine.eligibility import assess
    policy = s["policy"]
    # Preliminary pricing at grade B; re-priced after the risk model grades the case.
    rate = _rate(s["form"], "B", policy)
    elig, hits = assess(s["form"], s["bundle"], s["bank"], policy, rate)
    summary = (f"Income used {_fmt_inr(elig.assessed_income)}/m; FOIR {elig.foir_actual:.1%} vs cap "
               f"{elig.foir_cap:.0%}; LTV {elig.ltv_actual:.1%} vs cap {elig.ltv_cap:.0%}; "
               f"max eligible {_fmt_inr(elig.max_eligible_loan)}")
    return ({"eligibility": elig, "eligibility_hits": hits}, summary,
            {"foir": elig.foir_actual, "ltv": elig.ltv_actual, "max_eligible": elig.max_eligible_loan,
             "rate": rate, "rules": [h.rule_id for h in _non_pass(hits)]})


def node_fraud_compliance(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.engine import compliance, fraud
    policy = s["policy"]
    f_hits = fraud.run(s["form"], s["bundle"], s["bank"], policy)
    c_hits = compliance.run(s["form"], s["bundle"], policy)
    bad = _non_pass(f_hits + c_hits)
    fails = [h.rule_id for h in bad if h.outcome == RuleOutcome.FAIL]
    for h in bad:
        audit_log.append(s["audit"], "system", "RULE_FIRED", f"{h.rule_id} {h.outcome.value}: {h.detail}",
                         {"rule_id": h.rule_id, "outcome": h.outcome.value, "effect": h.effect})
    summary = (f"{len(f_hits)} fraud + {len(c_hits)} compliance checks; "
               f"{len(bad)} non-pass ({', '.join(fails) or 'no failures'})")
    return ({"fraud_hits": f_hits, "compliance_hits": c_hits}, summary,
            {"non_pass": [h.rule_id for h in bad]})


def node_risk(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.engine.eligibility import assess
    from app.ml.features import build_features
    from app.ml.scorer import score
    policy = s["policy"]
    features = build_features(s["form"], s["bundle"], s["bank"], s["eligibility"])
    risk = score(features)
    update: dict[str, Any] = {"risk": risk, "features": features}
    final_rate = _rate(s["form"], risk.grade, policy)
    repriced = abs(final_rate - s["eligibility"].rate) > 1e-9
    if repriced:
        elig, hits = assess(s["form"], s["bundle"], s["bank"], policy, final_rate)
        update.update({"eligibility": elig, "eligibility_hits": hits})
    top = ", ".join(r.label for r in risk.reasons[:3])
    summary = (f"PD {risk.pd:.2%} → grade {risk.grade} ({risk.band}); model {risk.model_version}; "
               f"top drivers: {top or 'n/a'}"
               + (f"; re-priced at {final_rate:.2%}" if repriced else ""))
    return (update, summary, {"pd": risk.pd, "grade": risk.grade, "score": risk.score,
                              "model_version": risk.model_version, "rate": final_rate})


def node_capacity(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.capacity.forecast import assess
    from app.engine.finance import emi
    elig = s["eligibility"]
    # Stress the EMI the engine could actually sanction (requested amount capped at max eligible).
    amount = min(elig.requested_amount, elig.max_eligible_loan) if elig.max_eligible_loan > 0 else elig.requested_amount
    months = elig.tenure_months or min(s["form"].tenure_months, elig.max_tenure_months) or s["form"].tenure_months
    proposed = elig.requested_emi if amount >= elig.requested_amount else float(emi(amount, elig.rate, months))
    from app.schemas import Product
    # Home-loan purchase: current rent stops once the borrower moves in, so it is added back to cash flow.
    cap = assess(s["bank"], s["bundle"].transactions, proposed, s["policy"], seed=42,
                 annual_rate=elig.rate, tenure_months=months,
                 rent_ceases=s["form"].product == Product.HOME_LOAN)
    summary = (f"Health score {cap.health_score:.0f}/100; proposed EMI {_fmt_inr(proposed)}; surplus after EMI "
               f"{_fmt_inr(cap.monthly_surplus_after_emi)}/m; P(shortfall) {cap.prob_shortfall:.1%} "
               f"over {cap.iterations} Monte Carlo paths; stress coverage {cap.stress_emi_coverage:.2f}x")
    return ({"capacity": cap}, summary,
            {"health_score": cap.health_score, "prob_shortfall": cap.prob_shortfall, "proposed_emi": proposed,
             "stress_emi_coverage": cap.stress_emi_coverage})


def node_decision(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.engine.decision import decide
    hits = all_rule_hits(s)
    dec = decide(s["form"], s["eligibility"], s["risk"], s["capacity"], hits,
                 s["bundle"], s["policy"], s["started_at"])
    if not dec.rules_fired:
        dec.rules_fired = hits
    summary = (f"{dec.outcome.value}: sanction {_fmt_inr(dec.sanctioned_amount)} @ {dec.rate:.2%} for "
               f"{dec.tenure_months}m (EMI {_fmt_inr(dec.emi)}); {len(dec.conditions)} condition(s); "
               f"model suggested {dec.model_suggested.value}")
    return ({"decision": dec}, summary,
            {"outcome": dec.outcome.value, "engine_outcome": dec.engine_outcome.value,
             "model_suggested": dec.model_suggested.value, "sanctioned_amount": dec.sanctioned_amount,
             "reasons": dec.reasons, "conditions": [c.code for c in dec.conditions]})


def node_memo(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    from app.reports.memo import credit_memo
    dec = s["decision"]
    case = CaseDetail(
        id=s["case_id"], persona_id=s.get("persona_id"), created_at=s["started_at"],
        status=status_for(dec, s["bundle"]), form=s["form"],
        applicant=build_applicant(s["form"], s["bundle"]), bundle=s["bundle"], bank=s["bank"],
        eligibility=s["eligibility"], risk=s["risk"], capacity=s["capacity"], decision=dec,
    )
    case.memo_markdown = credit_memo(case)
    return ({"case": case}, f"Credit memo drafted ({len(case.memo_markdown):,} chars)",
            {"chars": len(case.memo_markdown)})


def node_audit(s: CopilotState) -> tuple[dict[str, Any], str, dict[str, Any]]:
    case = s["case"]
    ms = int((time.perf_counter() - s["t0"]) * 1000)
    if not case.decision.turnaround_ms:
        case.decision.turnaround_ms = ms
    return ({}, f"Case {case.id} finalised as {case.status.value} in {ms} ms; audit chain sealed",
            {"status": case.status.value, "turnaround_ms": ms})


_NODES: dict[str, NodeFn] = {
    "intake": node_intake, "documents": node_documents, "missing_docs_check": node_missing_docs,
    "bank_analytics": node_bank, "eligibility": node_eligibility,
    "fraud_compliance": node_fraud_compliance, "risk_model": node_risk, "capacity": node_capacity,
    "decision": node_decision, "credit_memo": node_memo, "audit": node_audit,
}


def _wrap(name: str, fn: NodeFn) -> Callable[[CopilotState], dict[str, Any]]:
    def run(state: CopilotState) -> dict[str, Any]:
        t = time.perf_counter()
        update, summary, data = fn(state)
        ms = round((time.perf_counter() - t) * 1000, 1)
        trace = list(state.get("trace", []))
        trace.append({"node": name, "ms": ms, "summary": summary, "status": "ok"})
        audit_log.append(state["audit"], _NODE_ACTORS.get(name, "system"), _NODE_ACTIONS[name],
                         summary, {"node": name, "ms": ms, **data})
        return {**update, "trace": trace, "audit": state["audit"]}
    return run


@lru_cache(maxsize=1)
def build_graph() -> Any:
    """Compile the Underwriting Copilot graph (cached)."""
    g: StateGraph = StateGraph(CopilotState)
    for name in NODE_ORDER:
        g.add_node(name, _wrap(name, _NODES[name]))  # type: ignore[call-overload]
    g.add_edge(START, NODE_ORDER[0])
    for a, b in itertools.pairwise(NODE_ORDER):
        g.add_edge(a, b)
    g.add_edge(NODE_ORDER[-1], END)
    return g.compile(name="Underwriting Copilot")


def run_graph(form: ApplicationForm, files: list[tuple[str, bytes]],
              persona_id: str | None = None, case_id: str | None = None) -> CaseDetail:
    """Run the full copilot graph and return a finished :class:`CaseDetail`."""
    started = datetime.now(timezone.utc)
    state: CopilotState = {
        "case_id": case_id or f"HL-{started:%y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        "persona_id": persona_id, "started_at": started, "t0": time.perf_counter(),
        "form": form, "files": files, "messages": [], "trace": [], "audit": [],
    }
    final: CopilotState = build_graph().invoke(state)
    case = final["case"]
    case.copilot_trace = list(final["trace"])
    for m in final.get("messages", []):
        case.copilot_trace.append({"node": "message", "ms": 0, "summary": m["text"], "status": "info",
                                   "message": m})
    case.audit = list(final["audit"])
    return case


__all__ = ["NODE_ORDER", "build_applicant", "build_graph", "run_graph", "status_for"]
