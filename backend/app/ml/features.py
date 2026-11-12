"""Feature contract for the PD model.

``build_features`` maps the case objects the pipeline already has
(``ApplicationForm``, ``DocumentBundle``, ``BankAnalytics``, ``Eligibility``)
to the flat numeric vector the model was trained on. The synthetic training
data (``app.ml.synthetic``) uses exactly these definitions.

Gender is deliberately NOT a feature (used only for fairness evaluation).
Missing evidence is imputed with neutral-to-conservative defaults listed in
``DEFAULTS`` so that a thin file never looks *better* than an average file.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from app.schemas import ApplicationForm, BankAnalytics, DocumentBundle, Eligibility, EmploymentType, Product

FEATURES: list[str] = [
    "bureau_score",
    "foir",
    "ltv",
    "monthly_income",
    "loan_to_income",
    "existing_emi_to_income",
    "bounces_6m",
    "amb_to_emi",
    "income_regularity",
    "cash_deposit_share",
    "high_risk_spend_share",
    "years_in_job",
    "age",
    "tenure_months",
    "is_self_employed",
    "is_lap",
    "has_co_applicant",
    "city_tier",
]

FEATURE_LABELS: dict[str, str] = {
    "bureau_score": "Credit bureau score",
    "foir": "Fixed obligations to income ratio (FOIR)",
    "ltv": "Loan to property value (LTV)",
    "monthly_income": "Assessed monthly income",
    "loan_to_income": "Loan amount vs annual income",
    "existing_emi_to_income": "Existing EMIs as share of income",
    "bounces_6m": "Cheque/NACH bounces in last 6 months",
    "amb_to_emi": "Average monthly balance vs proposed EMI",
    "income_regularity": "Regularity of income credits",
    "cash_deposit_share": "Cash deposits as share of credits",
    "high_risk_spend_share": "Spend on betting/crypto merchants",
    "years_in_job": "Years in current job / business",
    "age": "Applicant age",
    "tenure_months": "Loan tenure",
    "is_self_employed": "Self-employed applicant",
    "is_lap": "Loan against property (vs home loan)",
    "has_co_applicant": "Earning co-applicant",
    "city_tier": "City tier",
}

# Monotone direction used for LightGBM constraints and reason wording:
# +1 = higher value -> higher risk, -1 = higher value -> lower risk, 0 = unconstrained.
FEATURE_DIRECTION: dict[str, int] = {
    "bureau_score": -1,
    "foir": 1,
    "ltv": 1,
    "monthly_income": -1,
    "loan_to_income": 1,
    "existing_emi_to_income": 1,
    "bounces_6m": 1,
    "amb_to_emi": -1,
    "income_regularity": -1,
    "cash_deposit_share": 1,
    "high_risk_spend_share": 1,
    "years_in_job": -1,
    "age": 0,
    "tenure_months": 0,
    "is_self_employed": 1,
    "is_lap": 1,
    "has_co_applicant": -1,
    "city_tier": 1,
}

DEFAULTS: dict[str, float] = {
    "bureau_score": 720.0,        # no bureau pull -> slightly below portfolio median
    "amb_to_emi": 1.0,
    "income_regularity": 0.80,
    "cash_deposit_share": 0.10,
    "high_risk_spend_share": 0.0,
    "bounces_6m": 0.0,
    "age": 35.0,
}

TIER1 = {"mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai", "hyderabad", "kolkata",
         "pune", "ahmedabad", "gurugram", "gurgaon", "noida", "navi mumbai", "thane"}
TIER2 = {"nagpur", "indore", "jaipur", "lucknow", "surat", "kochi", "coimbatore", "chandigarh", "bhopal",
         "vadodara", "nashik", "visakhapatnam", "vizag", "mysuru", "mysore", "madurai", "ludhiana",
         "kanpur", "patna", "bhubaneswar", "dehradun", "raipur", "ranchi", "guwahati", "agra", "varanasi",
         "rajkot", "aurangabad", "thiruvananthapuram", "mangaluru", "mangalore", "vijayawada", "jodhpur",
         "faridabad", "ghaziabad", "amritsar", "goa", "panaji", "trichy", "tiruchirappalli", "hubli"}

_CASH_RE = re.compile(r"\b(cash\s*dep|by\s*cash|cash\s*deposit|cdm|cash)\b", re.I)


def city_tier(city: str | None) -> float:
    if not city:
        return 2.0
    c = city.strip().lower()
    if c in TIER1:
        return 1.0
    if c in TIER2:
        return 2.0
    return 3.0


def _age(form: ApplicationForm, bundle: DocumentBundle, on: date | None = None) -> float:
    dob: Any = form.dob or bundle.identity.get("dob")
    if isinstance(dob, str):
        try:
            dob = date.fromisoformat(dob[:10])
        except ValueError:
            dob = None
    if not isinstance(dob, date):
        return DEFAULTS["age"]
    on = on or date.today()
    return round((on - dob).days / 365.25, 1)


def _safe_ratio(num: float, den: float, default: float) -> float:
    if den is None or den <= 0 or num is None or not math.isfinite(num):
        return default
    return float(num) / float(den)


def _income_regularity(form: ApplicationForm, bank: BankAnalytics) -> float:
    if bank.months_covered <= 0:
        return DEFAULTS["income_regularity"]
    if form.employment_type == EmploymentType.SALARIED and bank.salary_regularity > 0:
        return float(min(max(bank.salary_regularity, 0.0), 1.0))
    credits = [float(m.get("credits", 0) or 0) for m in bank.monthly if isinstance(m, dict)]
    credits = [c for c in credits if c > 0]
    if len(credits) >= 2:
        mean = sum(credits) / len(credits)
        var = sum((c - mean) ** 2 for c in credits) / len(credits)
        cv = math.sqrt(var) / mean if mean > 0 else 1.0
        coverage = min(len(credits) / max(bank.months_covered, 1.0), 1.0)
        return round(max(0.0, min(1.0, coverage * (1.0 - min(cv, 1.0)))), 3)
    if bank.salary_regularity > 0:
        return float(bank.salary_regularity)
    return DEFAULTS["income_regularity"]


def _cash_share(bundle: DocumentBundle, bank: BankAnalytics) -> float:
    credits = [t for t in bundle.transactions if t.amount > 0]
    total = sum(t.amount for t in credits)
    if total > 0:
        cash = sum(
            t.amount for t in credits
            if (t.category or "").upper() == "CASH_DEPOSIT" or (not t.category and _CASH_RE.search(t.description))
        )
        return round(cash / total, 4)
    if bank.avg_monthly_credits > 0 and bank.cash_deposit_spikes:
        spikes = sum(abs(float(s.get("amount", 0) or 0)) for s in bank.cash_deposit_spikes)
        return round(min(spikes / (bank.avg_monthly_credits * max(bank.months_covered, 1.0)), 1.0), 4)
    return DEFAULTS["cash_deposit_share"] if bank.months_covered <= 0 else 0.0


def _high_risk_share(bundle: DocumentBundle, bank: BankAnalytics) -> float:
    if not bank.high_risk_merchants:
        return 0.0
    hr = sum(abs(float(m.get("amount", 0) or 0)) for m in bank.high_risk_merchants if isinstance(m, dict))
    debits = sum(-t.amount for t in bundle.transactions if t.amount < 0)
    if debits <= 0:
        debits = bank.avg_monthly_debits * max(bank.months_covered, 1.0)
    return round(min(_safe_ratio(hr, debits, 0.0), 1.0), 4)


def build_features(
    form: ApplicationForm,
    bundle: DocumentBundle,
    bank: BankAnalytics,
    eligibility: Eligibility,
) -> dict[str, float]:
    """Map case objects to the model's feature vector (all floats, keys == FEATURES)."""
    income = eligibility.assessed_income or form.declared_monthly_income + (
        form.co_applicant.monthly_net_income if form.co_applicant else 0.0
    )
    income = max(float(income), 1.0)
    existing = eligibility.existing_obligations if eligibility.existing_obligations is not None else form.existing_emi
    emi = eligibility.requested_emi or 0.0
    foir = eligibility.foir_actual if eligibility.foir_actual else (existing + emi) / income
    ltv = eligibility.ltv_actual if eligibility.ltv_actual else _safe_ratio(form.loan_amount, form.property_value, 0.8)
    loan = eligibility.requested_amount or form.loan_amount
    has_bank = bank.months_covered > 0

    feats: dict[str, float] = {
        "bureau_score": float(form.bureau_score) if form.bureau_score else DEFAULTS["bureau_score"],
        "foir": round(float(foir), 4),
        "ltv": round(float(ltv), 4),
        "monthly_income": round(income, 0),
        "loan_to_income": round(loan / (income * 12), 3),
        "existing_emi_to_income": round(float(existing) / income, 4),
        "bounces_6m": float(bank.bounces) * (6.0 / bank.months_covered if bank.months_covered > 6 else 1.0)
        if has_bank else DEFAULTS["bounces_6m"],
        "amb_to_emi": round(_safe_ratio(bank.avg_monthly_balance, emi, DEFAULTS["amb_to_emi"]), 3)
        if has_bank else DEFAULTS["amb_to_emi"],
        "income_regularity": _income_regularity(form, bank),
        "cash_deposit_share": _cash_share(bundle, bank),
        "high_risk_spend_share": _high_risk_share(bundle, bank),
        "years_in_job": float(form.years_in_job),
        "age": _age(form, bundle),
        "tenure_months": float(form.tenure_months),
        "is_self_employed": 1.0 if form.employment_type == EmploymentType.SELF_EMPLOYED else 0.0,
        "is_lap": 1.0 if form.product == Product.LAP else 0.0,
        "has_co_applicant": 1.0 if form.co_applicant and form.co_applicant.monthly_net_income > 0 else 0.0,
        "city_tier": city_tier(form.property_city or form.city),
    }
    for k, v in feats.items():
        if v is None or not math.isfinite(v):
            feats[k] = DEFAULTS.get(k, 0.0)
    return feats


def display_value(feature: str, value: float) -> str:
    """Human display of a feature value (used in reasons and UI)."""
    if feature in ("foir", "ltv", "existing_emi_to_income", "income_regularity",
                   "cash_deposit_share", "high_risk_spend_share"):
        return f"{value * 100:.0f}%"
    if feature == "monthly_income":
        return f"₹{value:,.0f}/month"
    if feature == "loan_to_income":
        return f"{value:.1f}x annual income"
    if feature == "amb_to_emi":
        return f"{value:.1f}x EMI"
    if feature == "tenure_months":
        return f"{value / 12:.0f} years"
    if feature in ("years_in_job", "age"):
        return f"{value:.1f} years" if feature == "years_in_job" else f"{value:.0f} years"
    if feature in ("is_self_employed", "is_lap", "has_co_applicant"):
        return "Yes" if value >= 0.5 else "No"
    if feature in ("bureau_score", "bounces_6m", "city_tier"):
        return f"{value:.0f}"
    return f"{value:g}"
