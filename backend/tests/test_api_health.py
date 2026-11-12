"""System / policy / persona endpoints."""
from __future__ import annotations

from api_support import client, require_personas


def test_health() -> None:
    r = client().get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True
    assert body["llm"]["label"] == "grounded-template"  # COPILOT_LLM=none in tests
    assert "documents.pipeline" in body["modules"]


def test_root_and_openapi_tags() -> None:
    assert client().get("/").status_code == 200
    spec = client().get("/openapi.json").json()
    paths = spec["paths"]
    for p in ["/api/health", "/api/policy", "/api/personas", "/api/personas/{persona_id}",
              "/api/personas/{persona_id}/files/{filename}", "/api/cases", "/api/cases/from-persona/{persona_id}",
              "/api/cases/{case_id}", "/api/cases/{case_id}/documents/{doc_id}", "/api/cases/{case_id}/override",
              "/api/cases/{case_id}/copilot", "/api/cases/{case_id}/memo", "/api/cases/{case_id}/sanction-letter",
              "/api/portfolio", "/api/model-card", "/api/demo/reset"]:
        assert p in paths, p
    assert {t["name"] for t in spec["tags"]} >= {"cases", "copilot", "reports"}


def test_cors_header() -> None:
    r = client().get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")


def test_policy() -> None:
    body = client().get("/api/policy").json()
    assert body["version"] == body["policy"]["version"]
    assert "ELG-FOIR-01" in body["rules"] and "LTV-HL-01" in body["rules"]


def test_model_card() -> None:
    r = client().get("/api/model-card")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_personas_list_and_detail() -> None:
    ps = require_personas()
    r = client().get("/api/personas")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == len(ps) >= 1
    first = items[0]
    assert first["expected_outcomes"], first
    d = client().get(f"/api/personas/{first['id']}").json()
    assert d["form"]["applicant_name"] == first["applicant_name"]
    f = client().get(f"/api/personas/{first['id']}/files/{first['files'][0]}")
    assert f.status_code == 200 and len(f.content) > 100


def test_not_found() -> None:
    assert client().get("/api/cases/NOPE").status_code == 404
    assert client().get("/api/personas/nope").status_code == 404
    assert client().get("/api/personas/p01/files/..%2F..%2Fsecret").status_code == 404
