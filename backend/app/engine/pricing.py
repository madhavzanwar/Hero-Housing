"""Risk-based pricing: base rate (product) + grade spread + self-employed spread, all from policy."""
from __future__ import annotations

from app.policy.loader import Policy
from app.schemas import ApplicationForm, EmploymentType, Product


def rate_for(form: ApplicationForm, grade: str, policy: Policy) -> float:
    pr = policy.section("pricing")
    base = float(pr["base_rate_lap"] if form.product == Product.LAP else pr["base_rate_home_loan"])
    spread = float(pr.get("grade_spread", {}).get(grade, pr.get("grade_spread", {}).get("E", 0.0)))
    if form.employment_type == EmploymentType.SELF_EMPLOYED:
        spread += float(pr.get("self_employed_spread", 0.0))
    return round(base + spread, 6)
