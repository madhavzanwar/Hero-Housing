from datetime import date

import pytest
from engine_factories import AS_OF, POLICY, bundle, form, statement

from app.engine import bank, eligibility
from app.engine.finance import emi, principal_from_emi
from app.schemas import CoApplicant, EmploymentType, Product, RuleOutcome

RATE = 0.0835


def run(f, b=None, tx=None, rate=RATE):
    b = b or bundle(net=f.declared_monthly_income)
    tx = statement(salary=f.declared_monthly_income) if tx is None else tx
    ba = bank.analyze(tx, POLICY)
    e, hits = eligibility.assess(f, b, ba, POLICY, rate, as_of=AS_OF)
    return e, {h.rule_id: h for h in hits}, ba


def test_clean_salaried_case():
    e, hits, _ = run(form())
    assert e.eligible
    assert e.assessed_income == pytest.approx(150000)
    assert e.foir_cap == 0.60 and hits["ELG-FOIR-03"].outcome == RuleOutcome.PASS
    assert e.ltv_rule_id == "LTV-HL-02" and e.ltv_actual == pytest.approx(4_500_000 / 6_200_000, abs=1e-4)
    assert e.requested_emi == pytest.approx(emi(4_500_000, RATE, 240), abs=0.01)
    assert e.max_loan_by_ltv == pytest.approx(4_960_000)
    assert e.max_eligible_loan == pytest.approx(min(e.max_loan_by_foir, e.max_loan_by_ltv), abs=1)
    assert e.tenure_options and all(o.tenure_months <= e.max_tenure_months for o in e.tenure_options)
    assert hits["BNK-BNC-01"].outcome == RuleOutcome.PASS
    assert all(h.reference for h in hits.values() if h.rule_id.startswith("LTV-HL"))


@pytest.mark.parametrize("income,cap", [(45000, 0.50), (90000, 0.55), (150000, 0.60), (300000, 0.65)])
def test_foir_band_applied(income, cap):
    f = form(declared_monthly_income=income, loan_amount=1_500_000, property_value=6_000_000)
    e, _, _ = run(f)
    assert e.foir_cap == cap
    assert e.max_emi_affordable == pytest.approx(cap * income, abs=1)


def test_income_is_minimum_of_sources():
    f = form(declared_monthly_income=160000)
    b = bundle(net=155000)
    e, _, _ = run(f, b, statement(salary=150000))
    assert e.assessed_income == pytest.approx(150000)


def test_detected_emi_used_when_higher_than_declared():
    f = form(declared_monthly_income=100000, existing_emi=5000, loan_amount=3_000_000, property_value=5_000_000)
    e, hits, ba = run(f, tx=statement(salary=100000, emi=21345.0))
    assert ba.total_detected_emi == pytest.approx(21345.0)
    assert e.existing_obligations == pytest.approx(21345.0)
    assert hits["BNK-EMI-01"].outcome == RuleOutcome.WARN


def test_foir_breach_reduce_amount():
    f = form(declared_monthly_income=100000, loan_amount=4_500_000, property_value=7_000_000)
    e, hits, _ = run(f, tx=statement(salary=100000, emi=25000.75))
    h = hits["ELG-FOIR-02"]
    assert h.outcome == RuleOutcome.FAIL and h.effect == "REDUCE_AMOUNT"
    expected = principal_from_emi(0.55 * 100000 - 25000.75, RATE, 240)
    assert e.max_loan_by_foir == pytest.approx(expected, abs=1)
    assert e.foir_actual > 0.55 and not e.eligible


def test_foir_breach_infeasible_declines():
    f = form(declared_monthly_income=40000, loan_amount=4_000_000, property_value=6_000_000)
    _, hits, _ = run(f, tx=statement(salary=40000, emi=12000.5))
    assert hits["ELG-FOIR-01"].effect == "DECLINE"


@pytest.mark.parametrize("loan,value,rid,cap,passes", [
    (2_700_000, 3_000_000, "LTV-HL-01", 0.90, True),     # exactly 90% at <= 30L
    (2_800_000, 3_100_000, "LTV-HL-01", 0.90, False),    # 90.3% (persona p12)
    (3_000_000, 3_750_000, "LTV-HL-01", 0.90, True),     # boundary 30L stays in 90% slab
    (3_100_000, 3_800_000, "LTV-HL-02", 0.80, False),    # 81.6% just above 30L
    (7_500_000, 9_375_000, "LTV-HL-02", 0.80, True),     # exactly 80% at 75L
    (7_600_000, 10_000_000, "LTV-HL-03", 0.75, False),   # 76% above 75L
])
def test_ltv_slabs_at_boundaries(loan, value, rid, cap, passes):
    f = form(declared_monthly_income=400000, loan_amount=loan, property_value=value)
    b = bundle(net=400000, property={"market_value": value, "consideration_value": value, "encumbrance": "NIL"})
    e, hits, _ = run(f, b, statement(salary=400000))
    assert e.ltv_rule_id == rid and e.ltv_cap == cap
    assert (hits[rid].outcome == RuleOutcome.PASS) is passes
    if not passes:
        assert hits[rid].effect == "REDUCE_AMOUNT"


def test_p12_reduce_to_279l():
    f = form(declared_monthly_income=90000, loan_amount=2_800_000, property_value=3_100_000)
    b = bundle(net=90000, property={"market_value": 3_100_000, "encumbrance": "NIL"})
    e, _, _ = run(f, b, statement(salary=90000))
    assert e.max_loan_by_ltv == pytest.approx(2_790_000)
    assert e.max_eligible_loan == pytest.approx(2_790_000)


def test_ltv_uses_lower_of_agreement_and_valuation():
    f = form(loan_amount=4_500_000, property_value=6_200_000)
    b = bundle(property={"market_value": 5_500_000, "consideration_value": 6_200_000, "encumbrance": "NIL"})
    e, _, _ = run(f, b)
    assert e.property_value == 5_500_000
    assert e.ltv_actual == pytest.approx(4_500_000 / 5_500_000, abs=1e-4)


def test_lap_caps_and_max():
    f = form(product=Product.LAP, employment_type=EmploymentType.SELF_EMPLOYED, declared_monthly_income=600000,
             loan_amount=8_000_000, property_value=15_000_000, property_type="COMMERCIAL", tenure_months=180,
             lap_end_use="Business expansion", years_in_job=10)
    b = bundle(salaried=False, income_docs={"type": "ITR", "years": [{"ay": "2025-26", "total_income": 7_800_000},
                                                                      {"ay": "2026-27", "total_income": 8_400_000}]},
               property={"market_value": 15_000_000, "encumbrance": "NIL"})
    e, hits, _ = run(f, b, statement(salary=0.0, salary_desc="NEFT CR CLINIC RECEIPTS"), rate=0.10)
    assert e.ltv_rule_id == "LTV-LAP-02" and e.ltv_cap == 0.55
    assert e.max_loan_by_ltv == pytest.approx(8_250_000)
    # ITR avg 81L/yr -> 6.75L/m x 0.9 = 6.075L > declared 6L -> declared is the minimum
    assert e.assessed_income <= 600000
    assert hits["LTV-LAP-02"].outcome == RuleOutcome.PASS
    assert e.max_tenure_months <= 180


def test_lap_max_loan_rule():
    f = form(product=Product.LAP, loan_amount=60_000_000, property_value=150_000_000, declared_monthly_income=3_000_000,
             tenure_months=180, lap_end_use="Business expansion")
    b = bundle(net=3_000_000, property={"market_value": 150_000_000, "encumbrance": "NIL"})
    e, hits, _ = run(f, b, statement(salary=3_000_000))
    assert hits["ELG-LAP-01"].effect == "REDUCE_AMOUNT"
    assert e.max_eligible_loan <= 50_000_000


def test_age_at_maturity_caps_tenure():
    # salaried born Nov-1972: 54 on AS_OF -> (60 - 54.0) * 12 = 71-72 months
    f = form(dob=date(1972, 11, 1), tenure_months=300)
    e, hits, _ = run(f)
    assert 70 <= e.max_tenure_months <= 72
    h = hits["ELG-TEN-01"]
    assert h.outcome == RuleOutcome.WARN and h.effect == "NONE"
    assert e.tenure_months == e.max_tenure_months
    assert e.age_at_maturity <= 60.0


def test_self_employed_gets_age_70():
    f = form(dob=date(1972, 11, 1), employment_type=EmploymentType.SELF_EMPLOYED, tenure_months=300, years_in_job=8)
    b = bundle(salaried=False, income_docs={"type": "ITR", "annual_income": 2_400_000})
    e, _, _ = run(f, b)
    assert e.max_tenure_months == 190 or 185 <= e.max_tenure_months <= 192


def test_tenure_below_minimum_declines():
    f = form(dob=date(1968, 1, 1), tenure_months=120)
    _, hits, _ = run(f)
    assert hits["ELG-TEN-01"].effect == "DECLINE"


def test_product_max_tenure():
    f = form(dob=date(1998, 1, 1), tenure_months=400)
    e, _, _ = run(f)
    assert e.max_tenure_months == 360


def test_co_applicant_income_added():
    co = CoApplicant(name="Neha Kulkarni", monthly_net_income=60000, existing_emi=4000)
    e1, _, _ = run(form(declared_monthly_income=50000, loan_amount=2_000_000, property_value=3_000_000))
    e2, _, _ = run(form(declared_monthly_income=50000, loan_amount=2_000_000, property_value=3_000_000, co_applicant=co))
    assert e2.assessed_income == pytest.approx(e1.assessed_income + 60000)
    assert e2.existing_obligations == pytest.approx(e1.existing_obligations + 4000)
    assert e2.max_loan_by_foir > e1.max_loan_by_foir


@pytest.mark.parametrize("score,effect", [(600, "DECLINE"), (680, "REFER"), (760, "NONE")])
def test_bureau_bands(score, effect):
    _, hits, _ = run(form(bureau_score=score))
    assert hits["ELG-BUR-01"].effect == effect


def test_bounces_refer_and_decline():
    def tx(n):
        return statement(extra=[(i, 10, "ECS RTN INSUFFICIENT FUNDS HDFC", 21345.0) for i in range(n)]
                         + [(i, 11, "ECS RETURN CHARGES", -590.0) for i in range(n)])
    _, h3, ba = run(form(), tx=tx(3))
    assert ba.bounces == 3 and h3["BNK-BNC-01"].effect == "REFER"
    _, h4, _ = run(form(), tx=tx(4))
    assert h4["BNK-BNC-01"].effect == "DECLINE"


def test_min_income_and_vintage():
    _, hits, _ = run(form(declared_monthly_income=20000, loan_amount=500_000, years_in_job=0.5))
    assert hits["ELG-INC-01"].effect == "DECLINE"
    assert hits["ELG-VIN-01"].effect == "REFER"


def test_low_amb_condition_and_short_statement():
    _, hits, _ = run(form(), tx=statement(months=3, start_balance=-400000))
    assert hits["BNK-AMB-01"].evidence["condition"] == "EMI_RESERVE"
    assert hits["BNK-STMT-01"].outcome == RuleOutcome.WARN
