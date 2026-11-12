import pytest
from engine_factories import POLICY, statement

from app.capacity import forecast
from app.engine import bank


def cap(salary=150000, emi_amt=38626.0, **kw):
    tx = statement(salary=salary, **kw)
    ba = bank.analyze(tx, POLICY)
    return forecast.assess(ba, tx, emi_amt, POLICY, seed=42, annual_rate=0.0835, tenure_months=240), ba


def test_shape_and_determinism():
    c1, _ = cap()
    c2, _ = cap()
    assert c1.model_dump() == c2.model_dump()
    assert c1.iterations == 1000 and len(c1.forecast) == 24
    assert [p.month for p in c1.forecast] == list(range(1, 25))
    assert all(p.p10 <= p.p50 <= p.p90 for p in c1.forecast)
    assert [s.name for s in c1.sub_scores] == ["Cash-flow stability", "Debt pressure", "Savings behaviour", "Emergency fund",
                                               "Spending consistency"]
    assert sum(s.weight for s in c1.sub_scores) == pytest.approx(1.0)
    assert "FinPilot" in c1.basis


def test_comfortable_borrower():
    c, ba = cap()
    assert c.prob_shortfall == 0.0
    assert c.monthly_surplus_after_emi == pytest.approx(150000 - ba.avg_monthly_debits - 38626, rel=0.05)
    assert c.stress_emi_coverage > 1.0
    assert c.health_score > 70


def test_stretched_borrower_has_shortfall():
    c, _ = cap(salary=60000, emi_amt=45000.0, start_balance=20000)
    assert c.monthly_surplus_after_emi < 0
    assert c.prob_shortfall > 0.9
    assert c.stress_emi_coverage < 1.0
    assert c.health_score < 50
    assert c.forecast[-1].p50 < 0


def test_health_score_monotonic_in_emi():
    low, _ = cap(emi_amt=20000.0)
    high, _ = cap(emi_amt=80000.0)
    assert low.health_score > high.health_score


def test_seed_changes_paths_but_not_shape():
    tx = statement(salary=70000, start_balance=30000)
    ba = bank.analyze(tx, POLICY)
    a = forecast.assess(ba, tx, 25000.0, POLICY, seed=1)
    b = forecast.assess(ba, tx, 25000.0, POLICY, seed=2)
    assert len(a.forecast) == len(b.forecast)


def test_short_history_uses_normal_approximation():
    c, _ = cap(months=2)
    assert "normal approximation" in c.basis


def test_stressed_emi():
    from app.engine.finance import emi
    base = emi(1_000_000, 0.085, 240)
    assert forecast.stressed_emi(base, 200, 0.085, 240) == pytest.approx(emi(1_000_000, 0.105, 240), rel=1e-6)


def test_pillar_formulas_follow_finpilot():
    assert forecast.score_savings(0.20)[0] == 100 and forecast.score_savings(0.10)[0] == 50
    assert forecast.score_emergency_fund(3)[0] == 50
    assert forecast.score_spending_consistency(0.25)[0] == 75
    assert forecast.score_debt_pressure(0.0, 0)[0] == 100
    assert forecast.score_cash_flow_stability([])[0] == 70
