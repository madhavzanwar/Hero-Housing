import pytest
from engine_factories import POLICY, bundle, doc, form, statement

from app.engine import bank, fraud
from app.engine.fraud import name_similarity, screen_name
from app.schemas import DocType, Flag, Product, RuleCategory, RuleOutcome, Severity, Transaction


def run(f=None, b=None, tx=None):
    f = f or form()
    b = b or bundle(net=f.declared_monthly_income)
    tx = statement(salary=f.declared_monthly_income) if tx is None else tx
    ba = bank.analyze(tx, POLICY)
    hits = fraud.run(f, b, ba, POLICY)
    by: dict[str, list] = {}
    for h in hits:
        by.setdefault(h.rule_id, []).append(h)
    return by, ba


def test_clean_case_has_no_adverse_effects():
    by, _ = run()
    assert all(h.effect == "NONE" for hs in by.values() for h in hs)
    assert by["FRD-NEG-01"][0].outcome == RuleOutcome.PASS
    assert by["FRD-INC-01"][0].outcome == RuleOutcome.PASS


def test_name_similarity():
    assert name_similarity("Vikram Rathore Singhania", "SINGHANIA VIKRAM RATHORE") == 1.0
    assert name_similarity("Mr. Vikram R Singhania", "Vikram Rathore Singhania") > 0.7
    assert name_similarity("Aarav Kulkarni", "Vikram Rathore Singhania") < 0.5


def test_pep_match_refers():
    by, _ = run(form(applicant_name="Vikram Rathore Singhania"),
                bundle(identity={"pan_masked": "XXXXX7319K", "name": "Vikram Rathore Singhania"}))
    h = by["FRD-NEG-01"][0]
    assert h.effect == "REFER" and h.evidence["list_type"] == "PEP" and h.evidence["pan_match"] is True
    assert "enhanced due diligence" in h.detail
    assert h.reference and "KYC" in h.reference


def test_sanctions_confirmed_declines_and_coapplicant_screened():
    from app.schemas import CoApplicant
    by, _ = run(form(co_applicant=CoApplicant(name="Rafiq Anwar Qureshi", monthly_net_income=10000)))
    h = by["FRD-NEG-01"][0]
    assert h.evidence["role"] == "Co-applicant" and h.effect == "DECLINE"


def test_defaulter_pan_mismatch_only_refers():
    m = screen_name("Arvind Kumar Tandulkar", "XXXXX0000A", POLICY)
    assert m and m[0]["pan_match"] is False
    by, _ = run(form(applicant_name="Arvind Kumar Tandulkar"), bundle(identity={"pan_masked": "XXXXX0000A"}))
    assert by["FRD-NEG-01"][0].effect == "REFER"
    by, _ = run(form(applicant_name="Arvind Kumar Tandulkar"), bundle(identity={"pan_masked": "XXXXX8812T"}))
    assert by["FRD-NEG-01"][0].effect == "DECLINE"


def test_income_inflation_decline_p07_style():
    f = form(declared_monthly_income=180000)
    b = bundle(net=180000)  # tampered slips claim 1.8L
    by, _ = run(f, b, statement(salary=85000))
    h = by["FRD-INC-01"][0]
    assert h.outcome == RuleOutcome.FAIL and h.effect == "DECLINE"
    assert h.evidence["gap"] > 0.4 and "₹1,80,000" in h.detail and "₹85,000" in h.detail


def test_income_inflation_moderate_refers():
    by, _ = run(form(declared_monthly_income=120000), bundle(net=100000), statement(salary=100000))
    h = by["FRD-INC-01"][0]
    assert h.effect == "REFER" and 0.15 < h.evidence["gap"] <= 0.40


def test_income_inflation_self_employed_vs_itr():
    f = form(employment_type="SELF_EMPLOYED", declared_monthly_income=300000, years_in_job=6)
    b = bundle(salaried=False, income_docs={"type": "ITR", "annual_income": 1_800_000})
    by, _ = run(f, b, statement(salary=0.0))
    assert by["FRD-INC-01"][0].effect == "DECLINE"  # 3L declared vs 1.5L ITR


def test_doc_flags_mapped_by_severity():
    flags = [
        Flag(code="DOC_FONT_ANOMALY", title="Font anomaly", detail="Net pay uses a different font", severity=Severity.CRITICAL,
             document_id="salary_slip-0"),
        Flag(code="DOC_PDF_PRODUCER", title="Edited PDF", detail="Producer iLovePDF", severity=Severity.HIGH),
        Flag(code="ADDRESS_MISMATCH", title="Address differs", detail="PAN ABCPZ1234F address differs", severity=Severity.MEDIUM),
        Flag(code="INCOME_INFLATION", title="ignored", detail="computed by engine", severity=Severity.CRITICAL),
    ]
    by, _ = run(b=bundle(flags=flags))
    effects = {h.evidence["flag_code"]: h for h in by["FRD-DOC-01"]}
    assert effects["DOC_FONT_ANOMALY"].effect == "DECLINE" and effects["DOC_FONT_ANOMALY"].category == RuleCategory.FRAUD
    assert effects["DOC_PDF_PRODUCER"].effect == "REFER"
    assert effects["ADDRESS_MISMATCH"].effect == "CONDITION" and effects["ADDRESS_MISMATCH"].category == RuleCategory.DOCUMENT
    assert "ABCPZ1234F" not in effects["ADDRESS_MISMATCH"].detail
    assert "INCOME_INFLATION" not in effects


def test_suspicious_producer_metadata():
    b = bundle()
    b.documents.append(doc(DocType.SALARY_SLIP, 9, metadata={"producer": "iLovePDF", "creator": "Word"}))
    by, _ = run(b=b)
    assert by["FRD-DOC-02"][0].effect == "REFER"


def test_high_risk_merchants():
    extra = [(i, 18, f"UPI/DREAM11/{i}", -9350.0 - i) for i in range(6)] + [(i, 19, "UPI/RUMMYCIRCLE", -4410.0) for i in range(6)]
    by, ba = run(tx=statement(extra=extra))
    h = by["FRD-HRM-01"][0]
    assert {m["merchant"] for m in ba.high_risk_merchants} >= {"dream11", "rummy"}
    assert ba.high_risk_debit_share > 0.05 and h.effect == "REFER"


def test_high_risk_keyword_word_boundary():
    by, ba = run(tx=statement(extra=[(0, 18, "POS BETTER HOMES FURNITURE", -15250.0), (1, 18, "UPI/STAKEHOLDER MEETING", -820.0),
                                          (2, 18, "NEFT ALPHABET SOUP CO", -1210.0)]))
    assert ba.high_risk_merchants == []
    assert by["FRD-HRM-01"][0].outcome == RuleOutcome.PASS


def test_small_high_risk_share_is_info_only():
    by, _ = run(tx=statement(extra=[(0, 18, "UPI/POKERSTARS", -499.0)]))
    assert by["FRD-HRM-01"][0].effect == "NONE"


def test_round_numbers_flagged():
    from datetime import date, timedelta
    tx, bal = [], 100000.0
    for i in range(40):
        amt = 5000.0 if i % 2 else -3000.0
        bal += amt
        tx.append(Transaction(date=date(2026, 5, 1) + timedelta(days=4 * i), description=f"IMPS TRF {i}", amount=amt, balance=bal))
    by, ba = run(tx=tx)
    assert ba.round_number_share > 0.6
    assert by["FRD-RND-01"][0].effect == "REFER"


def test_duplicate_statements():
    b = bundle()
    b.documents.append(doc(DocType.BANK_STATEMENT, 0))  # same sha as the first statement
    by, _ = run(b=b)
    assert by["FRD-DUP-01"][0].effect == "REFER"
    tx = statement()
    by2, ba = run(tx=tx + tx)
    assert ba.duplicate_txn_share >= 0.5 and "FRD-DUP-01" in by2


def test_cash_spikes_and_share():
    lap = form(product=Product.LAP, lap_end_use="Business expansion")
    upi = [(i, day, "UPI/CR/CUSTOMER", 2911.0 + 13 * day + i) for i in range(6) for day in range(2, 28, 3)]
    by, ba = run(lap, tx=statement(extra=[*upi, (2, 14, "CASH DEP BRANCH INDORE", 120000.0)]))
    assert ba.cash_deposit_spikes and by["FRD-CASH-01"][0].evidence["condition"] == "END_USE_DECLARATION"
    assert by["FRD-CASH-02"][0].outcome == RuleOutcome.PASS
    heavy = [(i, 14, "BY CASH CDM 0091", 95000.0 + i) for i in range(6)]
    by, ba = run(tx=statement(extra=heavy))
    assert ba.cash_deposit_share > 0.3 and by["FRD-CASH-02"][0].effect == "REFER"
    assert by["FRD-CASH-01"][0].evidence["condition"] == "SOURCE_OF_FUNDS" if "FRD-CASH-01" in by else True


@pytest.mark.parametrize("name", ["Vikram Rathore Singhania", "SINGHANIA VIKRAM RATHORE", "Vikram Rathor Singhania"])
def test_p11_variants_match(name):
    assert screen_name(name, None, POLICY)
