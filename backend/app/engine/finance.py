"""Loan maths and INR formatting helpers (reducing-balance, monthly compounding)."""
from __future__ import annotations

import math
from datetime import date


def emi(principal: float, annual_rate: float, months: int) -> float:
    """Equated monthly instalment: P*r*(1+r)^n / ((1+r)^n - 1), r = annual_rate/12."""
    if principal <= 0 or months <= 0:
        return 0.0
    r = annual_rate / 12.0
    if r == 0:
        return principal / months
    f = (1 + r) ** months
    return principal * r * f / (f - 1)


def principal_from_emi(emi_amount: float, annual_rate: float, months: int) -> float:
    """Inverse of `emi`: the principal an EMI can service over `months`."""
    if emi_amount <= 0 or months <= 0:
        return 0.0
    r = annual_rate / 12.0
    if r == 0:
        return emi_amount * months
    f = (1 + r) ** months
    return emi_amount * (f - 1) / (r * f)


def tenure_for_emi(principal: float, annual_rate: float, emi_amount: float) -> int | None:
    """Months needed to repay `principal` with `emi_amount` (None if EMI never covers interest)."""
    if principal <= 0:
        return 0
    r = annual_rate / 12.0
    if r == 0:
        return math.ceil(principal / emi_amount) if emi_amount > 0 else None
    if emi_amount <= principal * r:
        return None
    n = -math.log(1 - principal * r / emi_amount) / math.log(1 + r)
    return math.ceil(n - 1e-9)


def age_on(dob: date | None, on_date: date | None = None) -> float:
    """Age in fractional years on `on_date` (default today)."""
    if dob is None:
        return 0.0
    on = on_date or date.today()
    years = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
    last_bday_year = dob.year + years
    try:
        last = dob.replace(year=last_bday_year)
    except ValueError:  # 29-Feb
        last = date(last_bday_year, 2, 28)
    days = (on - last).days
    return round(years + days / 365.25, 2)


def round_down(amount: float, step: float = 10000) -> float:
    if step <= 0:
        return float(amount)
    return float(math.floor(max(amount, 0.0) / step + 1e-9) * step)


def fmt_inr(amount: float | None, decimals: int = 0) -> str:
    """Indian digit grouping: 4500000 -> '₹45,00,000'; 12345678.5 -> '₹1,23,45,679'."""
    if amount is None:
        return "₹0"
    neg = amount < 0
    value = round(abs(float(amount)), decimals)
    whole = int(value)
    frac = f"{value - whole:.{decimals}f}"[1:] if decimals > 0 else ""
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{'-' if neg else ''}₹{s}{frac}"


def fmt_inr_short(amount: float) -> str:
    """'₹45.0 L' / '₹1.10 Cr' style."""
    a = abs(amount)
    sign = "-" if amount < 0 else ""
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.1f} L"
    return fmt_inr(amount)


def pct(x: float, decimals: int = 1) -> str:
    return f"{x * 100:.{decimals}f}%"
