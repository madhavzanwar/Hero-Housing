from datetime import date

import pytest
from engine_factories import AS_OF, POLICY, STARTED, bundle, form, risk, statement

from app.capacity import forecast
from app.engine import bank, compliance, decision, eligibility, fraud, pricing
from app.engine.finance import emi
from app.schemas import DecisionOutcome as D
from app.schemas import EmploymentType, Product, RuleOutcome


def pipeline(f, b=None, tx=None, grade="A", pd=0.015, with_capacity=True):
    b = b or bundle(net=f.declared_monthly_income)
    tx = statement(salary=f.declared_monthly_income) if tx is None else tx
    ba = bank.analyze(tx, POLICY)
    base_rate = pricing.rate_for(f, "A", POLICY)
    e, hits = eligibility.assess(f, b, ba, POLICY, base_rate, as_of=AS_OF)
    hits += fraud.run(f, b, ba, POLICY) + compliance.run(f, b, POLICY)
    cap = forecast.assess(ba, tx, e.requested_emi, POLICY) if with_capacity else None
    return decision.decide(f, e, risk(grade, pd), cap, hits, b, POLICY, STARTED), e


def codes(d):
    return [c.code for c in d.conditions]


def test_clean_approve():
    d, _ = pipeline(form())
    assert d.outcome == D.APPROVE == d.engine_outcome
    assert d.model_suggested == D.APPROVE
    assert d.sanctioned_amount == 4_500_000
    assert d.rate == pytest.approx(0.0835)
    assert d.emi == pytest.approx(emi(4_500_000, 0.0835, 240), abs=0.01)
    assert d.conditions == []
    assert d.reasons[0].startswith("Approved for ₹45,00,000")
    assert 3 <= len(d.reasons) <= 5
    assert d.policy_version == POLICY.version and d.turnaround_ms >= 0
    assert any(h.rule_id == "RSK-PD-01" for h in d.rules_fired)
    assert any(h.rule_id == "CAP-MC-01" for h in d.rules_fired)


def test_ltv_breach_reduces_to_rounded_amount():
    f = form(declared_monthly_income=90000, loan_amount=2_800_000, property_value=3_100_000)
    b = bundle(net=90000, property={"market_value": 3_100_000, "consideration_value": 3_100_000, "encumbrance": "NIL"})
    d, _ = pipeline(f, b, statement(salary=90000))
    assert d.outcome == D.APPROVE_WITH_CONDITIONS
    assert d.sanctioned_amount == 2_790_000
    assert codes(d)[0] == "REDUCE_AMOUNT" and "₹27,90,000" in d.conditions[0].text
    assert d.conditions[0].params["binding"] == "LTV"
    assert "ADD_CO_APPLICANT" not in codes(d)  # co-applicant cannot cure LTV
    assert d.emi == pytest.approx(emi(2_790_000, d.rate, 240), abs=0.01)


def test_foir_breach_conditions_with_alternatives():
    f = form(declared_monthly_income=100000, loan_amount=4_000_000, property_value=7_000_000, tenure_months=180)
    d, e = pipeline(f, tx=statement(salary=100000, emi=22000.5))
    assert d.outcome == D.APPROVE_WITH_CONDITIONS
    assert d.sanctioned_amount < 4_000_000 and d.sanctioned_amount % 10_000 == 0
    assert d.sanctioned_amount <= e.max_eligible_loan
    cs = {c.code: c for c in d.conditions}
    assert cs["REDUCE_AMOUNT"].params["binding"] == "FOIR"
    assert cs["ADD_CO_APPLICANT"].params["additional_income"] > 0
    assert "INCREASE_TENURE" in cs and cs["INCREASE_TENURE"].params["tenure_months"] > 180
    assert "CLEAR_EMI" in cs
    # the co-applicant income quoted really cures FOIR at the requested amount
    inc = e.assessed_income + cs["ADD_CO_APPLICANT"].params["additional_income"]
    _, cap = POLICY.foir_cap(inc)
    assert (e.existing_obligations + emi(4_000_000, d.rate, 180)) / inc <= cap + 1e-6
    t = cs["INCREASE_TENURE"].params["tenure_months"]
    assert (e.existing_obligations + emi(4_000_000, d.rate, t)) / e.assessed_income <= e.foir_cap + 1e-6


def test_borderline_refer_bureau_and_bounces():
    extra = [(i, 10, "NACH RETURN INSUFFICIENT BAL", 15000.0) for i in range(3)]
    d, _ = pipeline(form(bureau_score=680), tx=statement(extra=extra))
    assert d.outcome == D.REFER
    assert d.sanctioned_amount > 0
    assert d.reasons[0].startswith("Referred")
    assert any("680" in r for r in d.reasons) and any("bounces" in r for r in d.reasons)


def test_income_inflation_declines_despite_good_model():
    f = form(declared_monthly_income=180000, loan_amount=4_000_000)
    d, _ = pipeline(f, bundle(net=180000), statement(salary=85000), grade="A")
    assert d.outcome == D.DECLINE
    assert d.sanctioned_amount == 0 and d.emi == 0 and d.conditions == []
    assert d.model_suggested == D.APPROVE
    assert d.reasons[0].startswith("Application declined")


def test_p08_old_applicant_low_income_high_ltv_declines():
    f = form(dob=date(1972, 6, 1), declared_monthly_income=45000, loan_amount=3_800_000, property_value=4_000_000,
             tenure_months=300)
    d, _ = pipeline(f, bundle(net=45000, property={"market_value": 4_000_000, "encumbrance": "NIL"}), statement(salary=45000))
    assert d.outcome == D.DECLINE


def test_grade_e_on_clean_file_becomes_refer():
    d, _ = pipeline(form(), grade="E", pd=0.4)
    assert d.outcome == D.REFER and d.model_suggested == D.DECLINE
    h = next(h for h in d.rules_fired if h.rule_id == "RSK-PD-01")
    assert h.effect == "REFER"


def test_grade_d_refers_and_c_adds_condition():
    assert pipeline(form(), grade="D", pd=0.15)[0].outcome == D.REFER
    d, _ = pipeline(form(), grade="C", pd=0.07)
    assert d.outcome == D.APPROVE_WITH_CONDITIONS and "RISK_PRICING" in codes(d)
    assert d.rate == pytest.approx(0.0835 + 0.006)


def test_amount_above_auto_limit_refers():
    f = form(declared_monthly_income=1_500_000, loan_amount=25_000_000, property_value=40_000_000)
    b = bundle(net=1_500_000, property={"market_value": 40_000_000, "encumbrance": "NIL"})
    d, _ = pipeline(f, b, statement(salary=1_500_000))
    assert d.outcome == D.REFER
    assert any(h.rule_id == "DEC-AMT-01" for h in d.rules_fired)


def test_pep_refers():
    f = form(applicant_name="Vikram Rathore Singhania")
    d, _ = pipeline(f, bundle(identity={"pan_masked": "XXXXX7319K"}))
    assert d.outcome == D.REFER
    assert any("politically exposed" in r for r in d.reasons)


def test_lap_prohibited_end_use_declines():
    f = form(product=Product.LAP, employment_type=EmploymentType.SELF_EMPLOYED, declared_monthly_income=250000,
             loan_amount=3_000_000, property_value=9_000_000, tenure_months=180, years_in_job=8,
             lap_end_use="Capital market investment in stocks")
    b = bundle(salaried=False, income_docs={"type": "ITR", "annual_income": 3_600_000},
               property={"market_value": 9_000_000, "encumbrance": "NIL", "owner": "Aarav Kulkarni"})
    d, _ = pipeline(f, b, statement(salary=250000, salary_desc="NEFT CR CLIENT RECEIPTS"))
    assert d.outcome == D.DECLINE
    assert any("prohibited" in r for r in d.reasons)


def test_lap_cash_spike_conditions():
    f = form(product=Product.LAP, employment_type=EmploymentType.SELF_EMPLOYED, declared_monthly_income=250000,
             loan_amount=3_500_000, property_value=7_000_000, tenure_months=180, years_in_job=8, lap_end_use="Business expansion")
    b = bundle(salaried=False, income_docs={"type": "ITR", "annual_income": 3_600_000},
               property={"market_value": 7_000_000, "encumbrance": "NIL", "owner": "Aarav Kulkarni"})
    upi = [(i, day, "UPI/CR/CUSTOMER PAYMENT", 3127.0 + 17 * day + i) for i in range(6) for day in range(2, 28, 3)]
    d, _ = pipeline(f, b, statement(salary=220000, salary_desc="NEFT CR TRADE RECEIPTS",
                                    extra=[*upi, (3, 14, "CASH DEP KIRANA COUNTER", 190000.0)]))
    assert d.outcome == D.APPROVE_WITH_CONDITIONS
    assert "END_USE_DECLARATION" in codes(d)
    assert d.rate == pytest.approx(0.0975 + 0.0025)


def test_missing_docs_and_encumbrance_conditions():
    b = bundle(property={"market_value": 6_200_000, "encumbrance": None})
    b.documents = [x for x in b.documents if x.doc_type.value != "FORM16"]
    d, _ = pipeline(form(), b)
    assert d.outcome == D.APPROVE_WITH_CONDITIONS
    assert {"SUBMIT_DOC", "LEGAL_TITLE"} <= set(codes(d))
    sub = next(c for c in d.conditions if c.code == "SUBMIT_DOC")
    assert "Form 16" in sub.text


def test_tenure_cap_adds_reduce_tenure_condition():
    d, e = pipeline(form(dob=date(1975, 1, 1), tenure_months=300, loan_amount=2_000_000))
    assert d.tenure_months == e.max_tenure_months < 300
    assert "REDUCE_TENURE" in codes(d)


def test_decision_without_capacity_and_rules_have_refs():
    d, _ = pipeline(form(), with_capacity=False)
    assert d.outcome == D.APPROVE
    for h in d.rules_fired:
        assert h.rule_id in POLICY.section("rules") or h.rule_id.startswith(("ELG-FOIR", "LTV"))
        assert h.outcome in RuleOutcome


def test_model_action_mapping():
    assert decision.model_action("A", POLICY) == D.APPROVE
    assert decision.model_action("C", POLICY) == D.APPROVE_WITH_CONDITIONS
    assert decision.model_action("D", POLICY) == D.REFER
    assert decision.model_action("E", POLICY) == D.DECLINE


def test_pricing_grid():
    f = form()
    assert pricing.rate_for(f, "B", POLICY) == pytest.approx(0.086)
    se = form(employment_type=EmploymentType.SELF_EMPLOYED)
    assert pricing.rate_for(se, "A", POLICY) == pytest.approx(0.086)
    lap = form(product=Product.LAP)
    assert pricing.rate_for(lap, "E", POLICY) == pytest.approx(0.0975 + 0.0175)
