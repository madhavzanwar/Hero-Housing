"""Repayment capacity: FinPilot's 5-pillar financial health score + bootstrap Monte Carlo
cash-flow forecast, re-used for mortgage underwriting.

Credit: ported from FinPilot (`backend/app/analytics/health_score.py` and
`backend/app/forecast/cashflow.py`). FinPilot projected a *daily* balance for a personal-finance
user; here the same method runs on a *monthly* horizon after adding the proposed EMI:

* Bootstrap: resample (with replacement, seeded) the historical monthly net cash flows
  (credits - debits, winsorised at median +/- 3 MAD so a one-off down payment does not dominate),
  subtract the proposed EMI, and accumulate from the latest balance for `horizon_months`.
  P10/P50/P90 of the cumulative buffer are taken across 1000 paths; `prob_shortfall` is the share
  of paths whose buffer goes below zero in any month.
* With fewer than 3 months of history we fall back (as FinPilot did) to a normal approximation
  with sigma = 15% of monthly credits.
* Stress test: +200 bps rate shock on the EMI and -15% income (policy.capacity).
* Health score pillars and weights follow FinPilot (cash-flow stability 0.30, debt pressure 0.25,
  savings 0.20, emergency fund 0.15, spending consistency 0.10), with inputs re-defined for a borrower.
"""
from __future__ import annotations

import statistics

import numpy as np

from app.engine.finance import emi as emi_fn
from app.engine.finance import fmt_inr, principal_from_emi
from app.policy.loader import Policy
from app.schemas import BankAnalytics, ForecastPoint, RepaymentCapacity, SubScore, Transaction

_DEFAULT_WEIGHTS = {"cash_flow": 0.30, "debt_pressure": 0.25, "savings": 0.20, "emergency_fund": 0.15,
                    "spending_consistency": 0.10}
_ASSUMED_RATE, _ASSUMED_TENURE = 0.0875, 240


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _winsorise(values: list[float]) -> list[float]:
    if len(values) < 3:
        return values
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values) or (abs(med) * 0.1 + 1.0)
    lo, hi = med - 3 * mad, med + 3 * mad
    return [min(max(v, lo), hi) for v in values]


def stressed_emi(proposed_emi: float, bps: int, annual_rate: float | None, tenure_months: int | None) -> float:
    rate = annual_rate if annual_rate is not None else _ASSUMED_RATE
    n = tenure_months or _ASSUMED_TENURE
    principal = principal_from_emi(proposed_emi, rate, n)
    return emi_fn(principal, rate + bps / 10000.0, n)


# --------------------------------------------------------------------------- FinPilot pillars
def score_cash_flow_stability(points: list[ForecastPoint]) -> tuple[float, str]:
    """FinPilot: 100 - gap_ratio x 150, extra -20 if the first gap is imminent (here: within 3 months)."""
    if not points:
        return 70.0, "No forecast available; default neutral score."
    gaps = [p for p in points if p.p10 < 0]
    score = 100.0 - len(gaps) / len(points) * 150.0
    if gaps and gaps[0].month <= 3:
        score -= 20.0
    detail = f"{len(gaps)}/{len(points)} forecast months show a P10 buffer below zero"
    return _clamp(score), detail


def score_debt_pressure(foir: float, bounces: int) -> tuple[float, str]:
    """FinPilot DTI component (0.7): decays to 0 at 50%... here at 70% FOIR (Indian FOIR caps 50-65%).
    Utilisation component (0.3) replaced by payment conduct: 100 - 25 per bounce."""
    dti_score = _clamp(100.0 - (foir / 0.70) * 100.0)
    conduct = _clamp(100.0 - 25.0 * bounces)
    return _clamp(0.7 * dti_score + 0.3 * conduct), f"FOIR {foir * 100:.0f}% incl. proposed EMI; {bounces} bounce(s)"


def score_savings(rate: float) -> tuple[float, str]:
    """FinPilot: 20% savings rate -> 100, 0% -> 0 (after the proposed EMI)."""
    return _clamp(rate / 0.20 * 100.0), f"{rate * 100:.0f}% of income left after spending and the new EMI"


def score_emergency_fund(months: float) -> tuple[float, str]:
    """FinPilot: 6 months of outgoings -> 100."""
    return _clamp(months / 6.0 * 100.0), f"{months:.1f} months of outgoings (incl. EMI) held as balance"


def score_spending_consistency(cov: float) -> tuple[float, str]:
    """FinPilot: CoV 0 -> 100, 1.0 -> 0."""
    return _clamp(100.0 - cov * 100.0), f"monthly spend coefficient of variation {cov:.2f}"


def assess(
    bank: BankAnalytics,
    transactions: list[Transaction],
    proposed_emi: float,
    policy: Policy,
    seed: int = 42,
    annual_rate: float | None = None,
    tenure_months: int | None = None,
    rent_ceases: bool = False,
) -> RepaymentCapacity:
    """`rent_ceases=True` (home-loan purchase of a self-occupied home): the rent seen in the statement is
    added back to monthly cash flow, since the EMI replaces it."""
    cfg = policy.section("capacity")
    iters = int(cfg.get("monte_carlo_iterations", 1000))
    horizon = int(cfg.get("horizon_months", 24))
    bps = int(cfg.get("rate_shock_bps", 200))
    shock = float(cfg.get("income_shock_pct", 0.15))
    weights = {**_DEFAULT_WEIGHTS, **(cfg.get("health_weights") or {})}
    rng = np.random.default_rng(seed)

    monthly = bank.monthly
    credits = [float(m["credits"]) for m in monthly]
    rent_back = bank.avg_monthly_rent if rent_ceases else 0.0
    debits = [max(float(m["debits"]) - rent_back, 0.0) for m in monthly]
    nets = _winsorise([c - d for c, d in zip(credits, debits, strict=False)])
    # inflows are measured as total monthly credits (salary or business receipts alike)
    mean_credit = statistics.fmean(credits) if credits else bank.income_estimate
    income = mean_credit or bank.income_estimate
    mean_debit = statistics.fmean(debits) if debits else 0.0
    mean_net = statistics.fmean(nets) if nets else 0.0
    start = bank.latest_balance or bank.avg_monthly_balance
    surplus = mean_net - proposed_emi

    if len(nets) >= 3:
        samples = rng.choice(np.array(nets), size=(iters, horizon), replace=True) - proposed_emi
        method = f"bootstrap of {len(nets)} months of net cash flow"
    else:
        sigma = max(0.15 * mean_credit, 1.0)
        samples = rng.normal(mean_net, sigma, size=(iters, horizon)) - proposed_emi
        method = "normal approximation (less than 3 months of history)"
    paths = start + np.cumsum(samples, axis=1)
    p10, p50, p90 = (np.percentile(paths, q, axis=0) for q in (10, 50, 90))
    forecast = [ForecastPoint(month=i + 1, p10=round(float(min(p10[i], p50[i])), 2), p50=round(float(p50[i]), 2),
                              p90=round(float(max(p90[i], p50[i])), 2)) for i in range(horizon)]
    prob_shortfall = float(np.mean(paths.min(axis=1) < 0))

    s_emi = stressed_emi(proposed_emi, bps, annual_rate, tenure_months) if proposed_emi > 0 else 0.0
    non_emi_spend = max(mean_debit, 0.0)
    stressed_surplus = mean_credit * (1 - shock) - non_emi_spend
    coverage = (stressed_surplus + 0.0) / s_emi if s_emi > 0 else 9.99
    # coverage: what remains of shocked inflows after current outgoings, per rupee of shocked EMI
    coverage = round(max(coverage, -9.99), 2)

    foir = (bank.total_detected_emi + proposed_emi) / income if income > 0 else 1.0
    savings_rate = surplus / income if income > 0 else 0.0
    ef_months = start / (mean_debit + proposed_emi) if (mean_debit + proposed_emi) > 0 else 6.0
    cov = statistics.pstdev(debits) / mean_debit if len(debits) > 1 and mean_debit > 0 else 0.0
    pillars = [
        ("Cash-flow stability", "cash_flow", score_cash_flow_stability(forecast)),
        ("Debt pressure", "debt_pressure", score_debt_pressure(foir, bank.bounces)),
        ("Savings behaviour", "savings", score_savings(savings_rate)),
        ("Emergency fund", "emergency_fund", score_emergency_fund(ef_months)),
        ("Spending consistency", "spending_consistency", score_spending_consistency(cov)),
    ]
    subs = [SubScore(name=n, score=round(sc, 1), weight=float(weights[k]), detail=d) for n, k, (sc, d) in pillars]
    health = _clamp(sum(s.score * s.weight for s in subs))

    basis = (f"FinPilot 5-pillar health score and {iters}-path Monte Carlo ({method}) over {horizon} months, "
             f"starting from a balance of {fmt_inr(start)} with the proposed EMI of {fmt_inr(proposed_emi)} deducted; "
             f"stress: +{bps} bps and -{shock * 100:.0f}% income"
             + (f"; current rent of {fmt_inr(rent_back)} assumed to stop after purchase." if rent_back else "."))
    return RepaymentCapacity(
        health_score=round(health, 1),
        sub_scores=subs,
        monthly_surplus_after_emi=round(surplus, 2),
        forecast=forecast,
        prob_shortfall=round(prob_shortfall, 4),
        stress_emi_coverage=coverage,
        iterations=iters,
        basis=basis,
    )
