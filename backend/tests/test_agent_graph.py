"""LangGraph Underwriting Copilot + audit chain + report helpers."""
from __future__ import annotations

from api_support import fake_case, require_personas, require_pipeline

from app.agent import audit as audit_log
from app.agent.graph import NODE_ORDER, build_graph
from app.reports import memo


def test_graph_compiles_with_all_nodes() -> None:
    g = build_graph()
    nodes = set(g.get_graph().nodes)
    for n in NODE_ORDER:
        assert n in nodes
    assert NODE_ORDER[0] == "intake" and NODE_ORDER[-1] == "audit"


def test_audit_chain_detects_tampering() -> None:
    case = fake_case()
    assert audit_log.verify(case.audit)["valid"]
    case.audit[0].detail = "tampered"
    v = audit_log.verify(case.audit)
    assert v["valid"] is False and v["broken_at"] == 0


def test_apr_exceeds_rate_with_fee() -> None:
    apr = memo.apr_approx(4000000, 0.086, 240, 20000)
    assert 0.086 < apr < 0.09
    assert memo.inr(12345678) == "₹1,23,45,678"


def test_letters_by_outcome() -> None:
    from app.schemas import DecisionOutcome
    case = fake_case()
    assert "Key Facts Statement" in memo.outcome_letter(case)
    assert "90 days" in memo.outcome_letter(case)
    case.decision.outcome = DecisionOutcome.DECLINE
    txt = memo.outcome_letter(case)
    assert "Letter of Regret" in txt and case.decision.reasons[0] in txt
    case.decision.outcome = DecisionOutcome.REFER
    assert "Referred" in memo.outcome_letter(case)


def test_run_graph_end_to_end() -> None:
    require_pipeline()
    from app.pipeline import run_case
    p = require_personas()[0]
    case = run_case(p.form, p.read_files(), persona_id=p.id)
    nodes = [t["node"] for t in case.copilot_trace if t["node"] != "message"]
    assert nodes == NODE_ORDER
    assert all(t["ms"] >= 0 and t["summary"] for t in case.copilot_trace)
    assert audit_log.verify(case.audit)["valid"]
    actions = {e.action for e in case.audit}
    assert {"CASE_CREATED", "DOCUMENT_INGESTED", "MODEL_SCORED", "DECISION", "CASE_FINALISED"} <= actions
    assert case.decision.outcome.value in case.memo_markdown
    assert case.applicant.pan_masked is None or case.applicant.pan_masked.startswith("X")
