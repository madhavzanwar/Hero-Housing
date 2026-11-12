"""Tests for the PD scorer (model + fallback) and the feature builder."""
from __future__ import annotations

import itertools
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from app.ml import scorer
from app.ml.features import FEATURE_LABELS, FEATURES, build_features, city_tier
from app.schemas import (
    ApplicationForm,
    BankAnalytics,
    CoApplicant,
    DocumentBundle,
    Eligibility,
    EmploymentType,
    Product,
    RiskScore,
    Transaction,
)

BASE: dict[str, float] = {
    "bureau_score": 750, "foir": 0.40, "ltv": 0.70, "monthly_income": 100_000, "loan_to_income": 2.5,
    "existing_emi_to_income": 0.05, "bounces_6m": 0, "amb_to_emi": 2.0, "income_regularity": 0.92,
    "cash_deposit_share": 0.05, "high_risk_spend_share": 0.0, "years_in_job": 5, "age": 35,
    "tenure_months": 240, "is_self_employed": 0, "is_lap": 0, "has_co_applicant": 0, "city_tier": 1,
}


@pytest.fixture(params=["model", "fallback"])
def mode(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    scorer.reset_cache()
    if request.param == "fallback":
        monkeypatch.setattr(scorer, "ARTIFACT_DIR", Path("/nonexistent/artifacts"))
    elif not (scorer.ARTIFACT_DIR / "model.txt").exists():
        pytest.skip("model artifacts not trained")
    yield request.param
    scorer.reset_cache()


def _valid(r: RiskScore) -> None:
    assert 0.0 < r.pd < 1.0
    assert 300 <= r.score <= 900
    assert r.grade in {"A", "B", "C", "D", "E"}
    assert r.band
    assert r.model_version and r.model_version != "unavailable"
    assert set(r.features) == set(FEATURES)


def test_valid_ranges_and_reasons(mode: str) -> None:
    r = scorer.score(BASE)
    _valid(r)
    assert 1 <= len(r.reasons) <= 5
    for reason in r.reasons:
        assert reason.feature in FEATURES
        assert reason.label == FEATURE_LABELS[reason.feature]
        assert reason.text.endswith(("increased risk", "reduced risk"))
        assert ("increased" in reason.text) == (reason.impact > 0)
    impacts = [abs(x.impact) for x in r.reasons]
    assert impacts == sorted(impacts, reverse=True)
    if mode == "fallback":
        assert r.model_version.startswith("fallback")
    else:
        assert r.model_version.startswith("lightgbm-pd-v1")


@pytest.mark.parametrize("feature,low,high", [
    ("foir", 0.30, 0.75),
    ("ltv", 0.50, 0.92),
    ("bounces_6m", 0, 4),
    ("cash_deposit_share", 0.0, 0.5),
    ("high_risk_spend_share", 0.0, 0.15),
])
def test_monotonic_risk_up(mode: str, feature: str, low: float, high: float) -> None:
    lo = scorer.score({**BASE, feature: low}).pd
    hi = scorer.score({**BASE, feature: high}).pd
    assert hi > lo, f"{feature}: PD {lo} -> {hi}"


@pytest.mark.parametrize("feature,low,high", [
    ("bureau_score", 650, 820),
    ("amb_to_emi", 0.3, 5.0),
    ("income_regularity", 0.4, 0.98),
])
def test_monotonic_risk_down(mode: str, feature: str, low: float, high: float) -> None:
    lo = scorer.score({**BASE, feature: low}).pd
    hi = scorer.score({**BASE, feature: high}).pd
    assert hi < lo, f"{feature}: PD {lo} -> {hi}"


def test_foir_sweep_non_decreasing(mode: str) -> None:
    pds = [scorer.score({**BASE, "foir": f / 100}).pd for f in range(20, 90, 5)]
    assert all(b >= a for a, b in itertools.pairwise(pds))
    assert pds[-1] > pds[0]


def test_risky_profile_grades_worse_and_explains(mode: str) -> None:
    risky = {**BASE, "bureau_score": 640, "foir": 0.72, "ltv": 0.9, "bounces_6m": 4, "amb_to_emi": 0.3,
             "income_regularity": 0.5, "high_risk_spend_share": 0.1}
    good = scorer.score(BASE)
    bad = scorer.score(risky)
    assert bad.pd > good.pd and bad.score < good.score
    assert "ABCDE".index(bad.grade) >= "ABCDE".index(good.grade)
    assert bad.grade in {"D", "E"}
    assert any(x.feature == "bureau_score" and x.impact > 0 for x in bad.reasons)
    assert any("Weak credit bureau score (640)" in x.text for x in bad.reasons)


def test_missing_and_garbage_values_are_imputed(mode: str) -> None:
    r = scorer.score({"foir": "n/a", "ltv": None})
    _valid(r)
    assert r.features["bureau_score"] == 720.0


def test_score_is_fast_and_deterministic(mode: str) -> None:
    first = scorer.score(BASE)
    t = time.perf_counter()
    for _ in range(20):
        r = scorer.score(BASE)
    assert (time.perf_counter() - t) / 20 < 0.2
    assert r.pd == first.pd and r.score == first.score


def test_grade_bands_and_score_scale() -> None:
    assert scorer.grade_for(0.01) == ("A", "Low")
    assert scorer.grade_for(0.05) == ("B", "Moderate")
    assert scorer.grade_for(0.07)[0] == "C"
    assert scorer.grade_for(0.15)[0] == "D"
    assert scorer.grade_for(0.5) == ("E", "Very high")
    assert scorer.pd_to_score(0.05) == 650
    assert scorer.pd_to_score(0.0005) == 900
    assert scorer.pd_to_score(0.99) == 300
    assert scorer.pd_to_score(0.01) > scorer.pd_to_score(0.02)


def test_model_info(mode: str) -> None:
    info = scorer.model_info()
    assert info["features"] == FEATURES
    assert info["status"] in {"lightgbm+platt", "fallback-scorecard"}
    assert len(info["pd_bands"]) == 5


# --------------------------------------------------------------------------- features
def _elig(**kw: float) -> Eligibility:
    base = dict(
        policy_version="t", assessed_income=120_000, income_basis="test", existing_obligations=10_000,
        foir_cap=0.6, foir_actual=0.45, ltv_cap=0.8, ltv_actual=0.75, ltv_rule_id="LTV-HL-02", rate=0.0835,
        max_tenure_months=300, age_at_maturity=55, max_emi_affordable=62_000, max_loan_by_foir=6_000_000,
        max_loan_by_ltv=4_960_000, max_eligible_loan=4_960_000, requested_amount=4_500_000,
        requested_emi=44_000, eligible=True,
    )
    base.update(kw)
    return Eligibility(**base)  # type: ignore[arg-type]


def _form(**kw: object) -> ApplicationForm:
    base: dict[str, object] = dict(
        applicant_name="Test Applicant", dob=date(1990, 5, 1), city="Pune", declared_monthly_income=120_000,
        existing_emi=10_000, bureau_score=780, loan_amount=4_500_000, property_value=6_000_000,
        tenure_months=240, years_in_job=6,
    )
    base.update(kw)
    return ApplicationForm(**base)  # type: ignore[arg-type]


def test_build_features_full_case() -> None:
    txns = [
        Transaction(date=date(2026, 6, 1), description="SALARY ACME", amount=120_000, category="SALARY"),
        Transaction(date=date(2026, 6, 3), description="CASH DEPOSIT BRANCH", amount=30_000),
        Transaction(date=date(2026, 6, 5), description="UPI DREAM11", amount=-5_000, category="GAMBLING"),
        Transaction(date=date(2026, 6, 6), description="RENT", amount=-45_000),
    ]
    bank = BankAnalytics(months_covered=6, avg_monthly_balance=88_000, salary_regularity=1.0, bounces=1,
                         high_risk_merchants=[{"merchant": "DREAM11", "amount": -5_000}])
    f = build_features(_form(co_applicant=CoApplicant(name="Spouse", monthly_net_income=40_000)),
                       DocumentBundle(transactions=txns), bank, _elig())
    assert list(f) == FEATURES
    assert all(isinstance(v, float) for v in f.values())
    assert f["bureau_score"] == 780
    assert f["foir"] == 0.45 and f["ltv"] == 0.75
    assert f["amb_to_emi"] == pytest.approx(2.0)
    assert f["cash_deposit_share"] == pytest.approx(0.2)
    assert f["high_risk_spend_share"] == pytest.approx(0.1)
    assert f["income_regularity"] == 1.0
    assert f["bounces_6m"] == 1
    assert f["has_co_applicant"] == 1 and f["city_tier"] == 1
    assert f["loan_to_income"] == pytest.approx(4_500_000 / (120_000 * 12), abs=1e-3)
    assert 30 < f["age"] < 40
    _valid(scorer.score(f))


def test_build_features_thin_file_defaults() -> None:
    form = _form(bureau_score=None, dob=None, city=None, employment_type=EmploymentType.SELF_EMPLOYED,
                 product=Product.LAP)
    f = build_features(form, DocumentBundle(), BankAnalytics(), _elig())
    assert f["bureau_score"] == 720.0
    assert f["age"] == 35.0
    assert f["amb_to_emi"] == 1.0 and f["income_regularity"] == 0.8
    assert f["is_self_employed"] == 1 and f["is_lap"] == 1 and f["has_co_applicant"] == 0
    assert f["city_tier"] == 2.0


def test_self_employed_regularity_from_monthly_credits() -> None:
    bank = BankAnalytics(months_covered=6, avg_monthly_balance=50_000,
                         monthly=[{"month": f"2026-0{i}", "credits": c} for i, c in
                                  enumerate([100_000, 110_000, 90_000, 105_000, 95_000, 100_000], start=1)])
    f = build_features(_form(employment_type=EmploymentType.SELF_EMPLOYED), DocumentBundle(), bank, _elig())
    assert 0.9 < f["income_regularity"] <= 1.0


def test_city_tier() -> None:
    assert city_tier("Mumbai") == 1 and city_tier(" bengaluru ") == 1
    assert city_tier("Indore") == 2 and city_tier("Nagpur") == 2
    assert city_tier("Bareilly") == 3 and city_tier(None) == 2
