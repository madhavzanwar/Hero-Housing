"""End-to-end document pipeline tests on the 12 generated personas (data/personas)."""
from __future__ import annotations

import json
import re

import pytest
from documents_support import COUNT_KEYS, PERSONA_DIR, PERSONA_IDS, bundle_for, expected, values_match

from app.schemas import DocType, Severity

pytestmark = pytest.mark.skipif(not (PERSONA_DIR / "p01" / "expected.json").exists(),
                                reason="run scripts/generate_personas.py first")

FULL_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
FULL_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_every_document_is_classified(pid: str) -> None:
    b = bundle_for(pid)
    exp = expected(pid)["documents"]
    got = {d.filename: d.doc_type.value for d in b.documents}
    assert got == {k: v["doc_type"] for k, v in exp.items()}
    assert all(d.classification_confidence >= 0.5 for d in b.documents)


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_no_missing_documents_and_ocr_used_for_scans(pid: str) -> None:
    b = bundle_for(pid)
    assert b.missing_documents == []
    for d in b.documents:
        if d.filename.endswith(".png"):
            assert d.ocr_engine != "pdf-text"
        else:
            assert d.ocr_engine == "pdf-text"


def _field_results(pid: str) -> list[tuple[str, str, object, object, bool]]:
    b = bundle_for(pid)
    exp = expected(pid)["documents"]
    out = []
    for d in b.documents:
        e = exp[d.filename]
        got = {f.name: f.value for f in d.fields}
        for key, val in e["fields"].items():
            if key in COUNT_KEYS:
                cat, sign = COUNT_KEYS[key]
                g: object = sum(1 for t in b.transactions if t.category == cat and (sign == 0 or t.amount * sign > 0))
            else:
                g = got.get(key)
            out.append((d.filename, key, g, val, values_match(g, val, e["source"] == "ocr")))
    return out


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_field_extraction_matches_expected(pid: str) -> None:
    res = _field_results(pid)
    misses = [r[:4] for r in res if not r[4]]
    # text-layer documents must be exact; allow at most one OCR miss per persona
    text_misses = [m for m in misses if m[0].endswith(".pdf")]
    assert not text_misses, text_misses
    assert len(misses) <= 1, misses


def test_overall_extraction_accuracy() -> None:
    res = [r for pid in PERSONA_IDS for r in _field_results(pid)]
    acc = sum(r[4] for r in res) / len(res)
    ocr = [r for r in res if r[0].endswith(".png")]
    ocr_acc = sum(r[4] for r in ocr) / len(ocr)
    assert acc >= 0.98, acc
    assert ocr_acc >= 0.93, ocr_acc


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_identity_and_property_facts(pid: str) -> None:
    b = bundle_for(pid)
    facts = expected(pid)["facts"]
    assert b.identity["pan_masked"] == facts["pan_masked"]
    assert b.identity["aadhaar_masked"] == facts["aadhaar_masked"]
    assert b.identity["dob"] == facts["dob"]
    assert values_match(b.identity["name"], facts["name"], ocr=True)
    assert b.property["market_value"] == pytest.approx(facts["property_market_value"])
    assert b.property["distress_value"] == pytest.approx(facts["property_distress_value"])
    assert b.property["consideration_value"] == pytest.approx(facts["consideration_value"])
    assert b.property["registration_no"] == facts["registration_no"]
    assert b.property["encumbrance"] == "NIL"


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_bank_statement_parsed_with_running_balance(pid: str) -> None:
    b = bundle_for(pid)
    stmt = next(d for d in b.documents if d.doc_type == DocType.BANK_STATEMENT)
    exp = expected(pid)["documents"]["bank_statement.pdf"]["fields"]
    assert len(b.transactions) == exp["n_transactions"]
    assert stmt.field("months_covered") >= expected(pid)["facts"]["statement_months"] - 0.5
    bal = exp["opening_balance"]
    for t in b.transactions:  # signed amounts reproduce the running balance
        bal = round(bal + t.amount, 2)
        assert t.balance == pytest.approx(bal, abs=0.01)
    assert all(t.category for t in b.transactions)


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_income_docs(pid: str) -> None:
    b = bundle_for(pid)
    facts = expected(pid)["facts"]
    if facts["employment_type"] == "SALARIED":
        assert b.income_docs["type"] == "FORM16"
        assert b.income_docs["annual_income"] == pytest.approx(facts["form16"]["gross_salary"])
        assert len(b.salary_slips) == 3
        assert [s["month"] for s in b.salary_slips] == ["2026-08", "2026-09", "2026-10"]
        assert all(s["net"] == pytest.approx(facts["slip_net_pay"]) for s in b.salary_slips)
    else:
        assert b.income_docs["type"] == "ITR"
        years = {y["ay"]: y["total_income"] for y in b.income_docs["years"]}
        assert years == {i["ay"]: i["total_income"] for i in facts["itr"]}


def test_p01_clean_has_no_high_flags() -> None:
    b = bundle_for("p01")
    assert [f for f in b.flags if f.severity in (Severity.HIGH, Severity.CRITICAL)] == []
    assert all(c.match for c in b.cross_checks)
    assert {c.field for c in b.cross_checks} >= {"name", "dob", "pan", "employer", "salary_vs_credit"}


@pytest.mark.parametrize("pid", [p for p in PERSONA_IDS if p != "p07"])
def test_genuine_personas_have_no_tamper_flags(pid: str) -> None:
    b = bundle_for(pid)
    bad = [f.code for f in b.flags if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    assert bad == [], bad


def test_p07_forgery_detected() -> None:
    b = bundle_for("p07")
    codes = {f.code for f in b.flags}
    assert set(expected("p07")["expected_flags"]) <= codes
    assert "DOC_TAMPERED" in codes and "FORM16_SLIP_MISMATCH" in codes
    assert any(f.severity == Severity.CRITICAL for f in b.flags)
    font = next(f for f in b.flags if f.code == "DOC_FONT_ANOMALY")
    assert font.evidence["odd_fonts"] == ["times"]
    assert "1,80,000.00" in font.evidence["odd_amounts"]
    sal = next(c for c in b.cross_checks if c.field == "salary_vs_credit")
    assert not sal.match and sal.values["salary_slip_net_avg"] == 180000


def test_p06_bounces_and_p10_gambling_and_p04_cash() -> None:
    assert sum(t.category == "BOUNCE" for t in bundle_for("p06").transactions) == 3
    g = [t for t in bundle_for("p10").transactions if t.category == "GAMBLING" and t.amount < 0]
    assert len(g) >= 60
    p04 = bundle_for("p04").transactions
    cash = sum(t.amount for t in p04 if t.category == "CASH_DEPOSIT")
    credits = sum(t.amount for t in p04 if t.amount > 0)
    assert 0.15 <= cash / credits <= 0.30


@pytest.mark.parametrize("pid", PERSONA_IDS)
def test_bundle_never_leaks_full_pan_or_aadhaar(pid: str) -> None:
    dumped = json.dumps(bundle_for(pid).model_dump(mode="json"))
    pans = [m for m in FULL_PAN.findall(dumped) if not m.startswith("XXXXX")]
    assert pans == []
    assert FULL_AADHAAR.findall(dumped) == []
