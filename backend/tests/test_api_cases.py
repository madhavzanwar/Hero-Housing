"""Case lifecycle: underwrite persona, list, fetch, documents, memo, letters, override, portfolio."""
from __future__ import annotations

import json

from api_support import client, persona_case, require_personas, require_pipeline


def _pid() -> str:
    return str(require_personas()[0].id)


def test_run_persona_case() -> None:
    require_pipeline()
    case = persona_case(_pid())
    assert case["decision"]["outcome"] in ("APPROVE", "APPROVE_WITH_CONDITIONS", "REFER", "DECLINE")
    assert case["decision"]["rules_fired"], "decision must carry rule hits"
    for h in case["decision"]["rules_fired"]:
        assert h["rule_id"] and h["detail"]
    nodes = [t["node"] for t in case["copilot_trace"]]
    for n in ["intake", "documents", "missing_docs_check", "bank_analytics", "eligibility", "fraud_compliance",
              "risk_model", "capacity", "decision", "credit_memo", "audit"]:
        assert n in nodes
    assert case["memo_markdown"]
    blob = json.dumps(case)
    assert "ABCPZ1234F" not in blob  # sample unmasked PAN must never appear


def test_list_get_and_documents() -> None:
    require_pipeline()
    case = persona_case(_pid())
    ids = [c["id"] for c in client().get("/api/cases").json()]
    assert case["id"] in ids
    got = client().get(f"/api/cases/{case['id']}").json()
    assert got["id"] == case["id"]
    doc = case["bundle"]["documents"][0]
    r = client().get(f"/api/cases/{case['id']}/documents/{doc['id']}")
    assert r.status_code == 200 and len(r.content) > 100
    assert client().get(f"/api/cases/{case['id']}/documents/missing").status_code == 404


def test_memo_contains_decision() -> None:
    require_pipeline()
    case = persona_case(_pid())
    r = client().get(f"/api/cases/{case['id']}/memo")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    md = r.text
    assert case["decision"]["outcome"] in md
    for section in ["Applicant", "Documents verified", "Income assessment", "Bank statement analytics",
                    "Eligibility", "Risk model", "Repayment capacity", "Rules fired", "Decision", "Conditions",
                    "Deviations & overrides"]:
        assert section in md, section
    letter = client().get(f"/api/cases/{case['id']}/sanction-letter").text
    assert letter.startswith("# ")


def test_audit_chain_valid() -> None:
    require_pipeline()
    case = persona_case(_pid())
    v = client().get(f"/api/cases/{case['id']}/audit/verify").json()
    assert v["valid"] is True and v["events"] >= 11


def test_override_flow() -> None:
    require_pipeline()
    case = client().post(f"/api/cases/from-persona/{_pid()}").json()
    cid = case["id"]
    bad = client().post(f"/api/cases/{cid}/override", json={"underwriter": "R. Iyer", "to_outcome": "REFER", "reason": ""})
    assert bad.status_code == 422
    target = "DECLINE" if case["decision"]["outcome"] != "DECLINE" else "APPROVE"
    r = client().post(f"/api/cases/{cid}/override",
                      json={"underwriter": "R. Iyer", "to_outcome": target, "reason": "Underwriter judgement after field visit"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "OVERRIDDEN"
    assert out["decision"]["outcome"] == target
    assert out["decision"]["engine_outcome"] == case["decision"]["engine_outcome"]
    assert out["decision"]["decided_by"] == "R. Iyer"
    assert out["overrides"][-1]["reason"].startswith("Underwriter judgement")
    assert out["audit"][-1]["action"] == "OVERRIDE"
    assert client().get(f"/api/cases/{cid}/audit/verify").json()["valid"] is True
    assert "R. Iyer" in client().get(f"/api/cases/{cid}/memo").text
    port = client().get("/api/portfolio").json()
    assert port["override_rate"] > 0


def test_multipart_upload() -> None:
    require_pipeline()
    p = require_personas()[0]
    files = [("files", (name, data, "application/octet-stream")) for name, data in p.read_files()]
    r = client().post("/api/cases", data={"form": p.form.model_dump_json()}, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["persona_id"] is None
    assert len(r.json()["bundle"]["documents"]) == len(files)


def test_multipart_bad_form() -> None:
    r = client().post("/api/cases", data={"form": "{not json"})
    assert r.status_code == 422


def test_portfolio() -> None:
    require_pipeline()
    persona_case(_pid())
    m = client().get("/api/portfolio").json()
    assert m["total_cases"] >= 1
    assert sum(m["by_outcome"].values()) == m["total_cases"]
    assert 0 <= m["approval_rate"] <= 1
