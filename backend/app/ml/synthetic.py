"""Synthetic Indian mortgage borrower dataset (SYNTHETIC — not real borrower data).

Why synthetic: no public, licence-clean dataset of Indian home-loan / LAP
borrowers exists with the features this app derives from a case file (FOIR,
LTV, bank-statement behaviour, ...). Public credit datasets (UCI Taiwan
credit-card default, German credit) are used only as an EXTERNAL BENCHMARK of
the modelling method (see ``backend/scripts/train_model.py``). The production PD model
is trained on the data generated here, so its absolute PD levels are only as
good as the assumptions below. They are documented so a credit team can
challenge them, and they must be re-estimated on the lender's own booked
portfolio before any real use.

Generative process (all draws from one seeded ``numpy.random.Generator``):

1.  ``city_tier`` ∈ {1, 2, 3} with p = (0.45, 0.35, 0.20).
2.  ``product``: LAP with p = 0.25, else HOME_LOAN.
3.  ``employment``: self-employed with p = 0.30 (HL) / 0.65 (LAP).
4.  ``gender`` (fairness evaluation only — never a model feature): F with
    p = 0.28.
5.  ``age``: salaried N(35, 7) clipped 21-58; self-employed N(41, 8)
    clipped 23-65; LAP borrowers +4 years.
6.  Latent credit quality ``z ~ N(0, 1)`` drives the bureau-visible
    behaviour; a separate unobserved shock ``u ~ N(0, 1)`` (job loss, medical
    event, ...) only affects default.
7.  ``monthly_income`` (net, ₹): log-normal with median 95k / 65k / 45k for
    tier 1 / 2 / 3, ×1.10 and wider dispersion for self-employed, rising ~1.5%
    per year of age 25→45, ×0.92 for women (observed gender pay gap); clipped
    ₹20k-₹20L. An earning co-applicant (p = 0.30, 0.45 for women) adds
    30-80% of the primary income to the assessed income.
8.  ``bureau_score`` = 745 + 50·z + N(0, 15), clipped 550-900.
9.  ``years_in_job``: salaried Gamma(2, 2.6), self-employed (business vintage)
    Gamma(3, 3); capped at age - 20.
10. ``existing_emi_to_income``: 0 with p = 0.45, else Beta(2, 8)·0.6, shifted
    up for weaker ``z``.
11. ``foir`` = existing + proposed EMI / income, with the proposed EMI share
    drawn from Beta(5, 7)·0.75 — i.e. most files sit inside policy caps but a
    tail breaches them (as in an application, not a booked, population).
12. ``tenure_months``: HL 120-360, LAP 60-180, cut to retirement age
    (60 salaried / 70 self-employed). Loan amount = principal from EMI at 8.5%
    (HL) / 10% (LAP). ``ltv``: HL Beta(6, 2.2)·0.97 (clipped 0.3-0.95), LAP
    Beta(5, 4)·0.75; property value = loan / LTV. ``loan_to_income`` = loan /
    annual income.
13. Bank-statement behaviour: ``bounces_6m`` ~ Poisson(exp(-2.4 - 0.8z)),
    ``amb_to_emi`` log-normal (median 1.8, higher for strong ``z``),
    ``income_regularity`` Beta(18, 1.5) salaried / Beta(5, 2) self-employed,
    ``cash_deposit_share`` Beta(1, 25) salaried / Beta(2, 6) self-employed
    (+ for tier 3), ``high_risk_spend_share`` 0 with p = 0.92 else Beta(1.2, 20).
14. Default (90+ DPD within 12 months equivalent) ~ Bernoulli(sigmoid(η)) with

    η = a + 0.02·(720 - bureau) + 1.0·(FOIR - 0.45) + 4·max(FOIR - 0.45, 0)
          + 6·max(FOIR - 0.65, 0) + 2.5·(LTV - 0.7) + 4·max(LTV - 0.85, 0)
          + 0.35·min(bounces, 5) - 0.35·ln(AMB/EMI) - 2·(regularity - 0.85)
          + 1.2·cash_share·(1.5 if salaried else 1) + 6·high_risk_share
          - 0.04·min(years_in_job, 15) + 0.25·SE + 0.25·LAP - 0.25·co_app
          + 0.15·(tier - 1) + 0.03·max(25 - age, 0) + 0.04·max(age - 50, 0)
          + 0.15·ln(LTI / 4) - 0.2·ln(income / 60k)
          + 0.6·u - 0.15·[gender = F]

    The intercept ``a`` is solved by bisection so the portfolio default rate
    equals ``target_default_rate`` (default 4%). The small negative gender term
    in the *unobserved* component mirrors bureau studies reporting lower
    delinquency for women borrowers in India; the model never sees gender,
    so the fairness evaluation can check calibration within groups.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TIER_MEDIAN_INCOME = {1: 95_000.0, 2: 65_000.0, 3: 45_000.0}


def _emi_to_principal(emi: np.ndarray, annual_rate: np.ndarray, months: np.ndarray) -> np.ndarray:
    r = annual_rate / 12.0
    return emi * (1 - (1 + r) ** (-months)) / r


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate(n: int = 60_000, seed: int = 42, target_default_rate: float = 0.04) -> pd.DataFrame:
    """Return a seeded synthetic borrower frame with model features + ``default`` + ``gender``."""
    rng = np.random.default_rng(seed)

    tier = rng.choice([1, 2, 3], size=n, p=[0.45, 0.35, 0.20])
    is_lap = (rng.random(n) < 0.25).astype(int)
    is_se = (rng.random(n) < np.where(is_lap == 1, 0.65, 0.30)).astype(int)
    gender = np.where(rng.random(n) < 0.28, "F", "M")
    is_f = gender == "F"

    age = np.where(is_se == 1, rng.normal(41, 8, n).clip(23, 65), rng.normal(35, 7, n).clip(21, 58))
    age = (age + 4 * is_lap).clip(21, 65)

    z = rng.normal(0, 1, n)          # latent credit quality (bureau-visible)
    u = rng.normal(0, 1, n)          # unobserved shock

    median = np.vectorize(TIER_MEDIAN_INCOME.get)(tier) * np.where(is_se == 1, 1.10, 1.0)
    age_lift = 1 + 0.015 * (np.clip(age, 25, 45) - 25)
    sigma = np.where(is_se == 1, 0.60, 0.50)
    income = median * age_lift * np.where(is_f, 0.92, 1.0) * np.exp(rng.normal(0, 1, n) * sigma + 0.1 * z)
    income = income.clip(20_000, 2_000_000)

    has_co = (rng.random(n) < np.where(is_f, 0.45, 0.30)).astype(int)
    co_income = has_co * income * rng.uniform(0.3, 0.8, n)
    assessed_income = income + co_income

    bureau = (745 + 50 * z + rng.normal(0, 15, n)).clip(550, 900).round()

    yij = np.where(is_se == 1, rng.gamma(3, 3, n), rng.gamma(2, 2.6, n))
    yij = np.minimum(yij, age - 20).clip(0.1, 40).round(1)

    has_emi = rng.random(n) > 0.45
    existing = np.where(has_emi, rng.beta(2, 8, n) * 0.6 * np.exp(-0.15 * z), 0.0).clip(0, 0.6)

    proposed_share = rng.beta(5, 7, n) * 0.75
    foir = (existing + proposed_share).clip(0.05, 1.2)
    emi = proposed_share * assessed_income

    max_age = np.where(is_se == 1, 70, 60)
    max_tenure_by_age = ((max_age - age) * 12).clip(36, None)
    tenure = np.where(
        is_lap == 1,
        rng.choice([60, 84, 120, 144, 180], n),
        rng.choice([120, 180, 240, 300, 360], n, p=[0.1, 0.2, 0.35, 0.15, 0.2]),
    )
    tenure = np.minimum(tenure, max_tenure_by_age).astype(int)
    rate = np.where(is_lap == 1, 0.10, 0.085)
    loan = _emi_to_principal(emi, rate, tenure)

    ltv = np.where(is_lap == 1, rng.beta(5, 4, n) * 0.75, rng.beta(6, 2.2, n) * 0.97).clip(0.2, 0.95)
    lti = loan / (assessed_income * 12)

    bounces = rng.poisson(np.exp(-2.4 - 0.8 * z))
    amb_to_emi = np.exp(np.log(1.8) + 0.4 * z + rng.normal(0, 0.6, n) + 0.3 * is_se).clip(0.05, 30)
    regularity = np.where(is_se == 1, rng.beta(5, 2, n), rng.beta(18, 1.5, n))
    regularity = (regularity - 0.03 * (z < -1.5)).clip(0, 1)
    cash_share = np.where(is_se == 1, rng.beta(2, 6, n), rng.beta(1, 25, n)) + 0.05 * (tier == 3)
    cash_share = cash_share.clip(0, 1)
    hr_share = np.where(rng.random(n) < 0.92, 0.0, rng.beta(1.2, 20, n))

    eta_wo_a = (
        0.02 * (720 - bureau)
        + 1.0 * (foir - 0.45) + 4 * np.maximum(foir - 0.45, 0) + 6 * np.maximum(foir - 0.65, 0)
        + 2.5 * (ltv - 0.7) + 4 * np.maximum(ltv - 0.85, 0)
        + 0.35 * np.minimum(bounces, 5)
        - 0.35 * np.log(amb_to_emi)
        - 2.0 * (regularity - 0.85)
        + 1.2 * cash_share * np.where(is_se == 1, 1.0, 1.5)
        + 6.0 * hr_share
        - 0.04 * np.minimum(yij, 15)
        + 0.25 * is_se + 0.25 * is_lap - 0.25 * has_co
        + 0.15 * (tier - 1)
        + 0.03 * np.maximum(25 - age, 0) + 0.04 * np.maximum(age - 50, 0)
        + 0.15 * np.log(np.maximum(lti, 0.2) / 4)
        - 0.2 * np.log(assessed_income / 60_000)
        + 0.6 * u - 0.15 * is_f
    )
    lo, hi = -15.0, 5.0
    for _ in range(60):  # bisection on intercept for target default rate
        mid = (lo + hi) / 2
        if _sigmoid(mid + eta_wo_a).mean() > target_default_rate:
            hi = mid
        else:
            lo = mid
    p = _sigmoid((lo + hi) / 2 + eta_wo_a)
    default = (rng.random(n) < p).astype(int)

    return pd.DataFrame({
        "bureau_score": bureau,
        "foir": foir.round(4),
        "ltv": ltv.round(4),
        "monthly_income": assessed_income.round(0),
        "loan_to_income": lti.round(3),
        "existing_emi_to_income": existing.round(4),
        "bounces_6m": bounces.astype(float),
        "amb_to_emi": amb_to_emi.round(3),
        "income_regularity": regularity.round(3),
        "cash_deposit_share": cash_share.round(4),
        "high_risk_spend_share": hr_share.round(4),
        "years_in_job": yij,
        "age": age.round(1),
        "tenure_months": tenure.astype(float),
        "is_self_employed": is_se.astype(float),
        "is_lap": is_lap.astype(float),
        "has_co_applicant": has_co.astype(float),
        "city_tier": tier.astype(float),
        "gender": gender,
        "true_pd": p.round(5),
        "default": default,
    })
