"""Bank-statement analytics: monthly aggregates, AMB, salary / EMI detection, bounces,
cash-deposit spikes and high-risk merchants.

Detection is keyword + recurrence based (transparent, auditable) and honours the
`category` the document layer may already have assigned to a transaction.
"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.policy.loader import Policy
from app.schemas import BankAnalytics, Transaction

SALARY_RE = re.compile(r"\b(SALARY|SAL|SAL CR|SALARY CR|PAYROLL|SLRY)\b", re.I)
EMI_RE = re.compile(r"\b(EMI|LOAN|LN)\b", re.I)
MANDATE_RE = re.compile(r"\b(NACH|ACH|ECS|SI|MANDATE)\b", re.I)
LENDER_HINT_RE = re.compile(r"\b(BANK|FINANCE|FINSERV|FIN|CAPITAL|HFC|HOUSING|CREDIT|LENDING|NBFC|HFL)\b", re.I)
NON_LOAN_RE = re.compile(
    r"\b(POWER|ELECTRIC\w*|BILL|INSURANCE|SIP|MUTUAL|MF|LIC|GAS|MOBILE|BROADBAND|DTH|WATER|PREMIUM|RENT)\b", re.I
)
BOUNCE_RE = re.compile(r"(RETURN|BOUNCE|INSUFFICIENT|INSUFF|ECS RTN|NACH RTN|\bRTN\b|DISHONOU?R|UNPAID|REVERSAL OF NACH)", re.I)
CHARGE_RE = re.compile(r"\b(CHARGE|CHARGES|CHG|CHGS|PENALTY|FEE)\b", re.I)
CASH_DEP_RE = re.compile(r"(CASH DEP|CASH DEPOSIT|\bCDM\b|BY CASH|CASH-DEP|CSH DEP)", re.I)
TRANSFER_HINT_RE = re.compile(r"\b(NEFT|IMPS|RTGS|UPI|TRF|TRANSFER)\b", re.I)
_LENDER_STOP = {
    "EMI", "NACH", "ACH", "LOAN", "ECS", "DR", "CR", "SI", "MANDATE", "DEBIT", "TO", "BY", "FOR",
    "AUTO", "PAY", "PAYMENT", "INST", "INSTALMENT", "INSTALLMENT", "A/C", "AC", "NO", "REF", "TXN", "LN",
}


def _month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _is(t: Transaction, cat: str) -> bool:
    return (t.category or "").upper() == cat


def is_bounce(t: Transaction) -> bool:
    if _is(t, "BOUNCE_CHARGE"):
        return False
    if _is(t, "BOUNCE"):
        return True
    return bool(BOUNCE_RE.search(t.description)) and not CHARGE_RE.search(t.description)


def is_cash_deposit(t: Transaction) -> bool:
    return t.amount > 0 and (_is(t, "CASH_DEPOSIT") or bool(CASH_DEP_RE.search(t.description)))


def is_salary(t: Transaction, employer: str | None = None) -> bool:
    if t.amount <= 0:
        return False
    if _is(t, "SALARY") or SALARY_RE.search(t.description):
        return True
    if employer:
        tok = [w for w in re.findall(r"[A-Za-z]{4,}", employer.upper()) if w not in {"PRIVATE", "LIMITED", "PVT", "LTD"}]
        desc = t.description.upper()
        return bool(tok) and tok[0] in desc and bool(TRANSFER_HINT_RE.search(desc))
    return False


def is_emi_debit(t: Transaction) -> bool:
    if t.amount >= 0 or is_bounce(t) or _is(t, "BOUNCE_CHARGE"):
        return False
    if _is(t, "EMI"):
        return True
    desc = t.description
    if CHARGE_RE.search(desc) or NON_LOAN_RE.search(desc):
        return False
    if EMI_RE.search(desc):
        return True
    return bool(MANDATE_RE.search(desc)) and bool(LENDER_HINT_RE.search(desc))


def _lender_key(desc: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z]+", desc.upper()) if len(w) > 1 and w not in _LENDER_STOP]
    return " ".join(words[:3]) or "UNKNOWN LENDER"


_HR_FALSE_POSITIVES = ("stakeholder", "better", "alphabet", "abet")


def high_risk_keyword(desc: str, keywords: list[str]) -> str | None:
    """Keyword match: very short keywords ("bet") need word boundaries on both sides (bet365 matches,
    'better' does not); longer ones only a leading boundary (rummycircle, pokerstars, stake.com)."""
    low = desc.lower()
    for fp in _HR_FALSE_POSITIVES:
        low = low.replace(fp, " ")
    for kw in keywords:
        k = kw.lower()
        pattern = rf"(?<![a-z]){re.escape(k)}(?![a-z])" if len(k) <= 3 else rf"(?<![a-z]){re.escape(k)}"
        if re.search(pattern, low):
            return kw
    return None


def _daily_balances(txns: list[Transaction]) -> dict[date, float]:
    """End-of-day balance for every calendar day in the statement (forward-filled)."""
    eod: dict[date, float] = {}
    running: float | None = None
    for t in txns:
        if t.balance is not None:
            running = t.balance
        elif running is not None:
            running += t.amount
        if running is not None:
            eod[t.date] = running
    if not eod:
        return {}
    days: dict[date, float] = {}
    d, end = min(eod), max(eod)
    last = eod[d]
    while d <= end:
        last = eod.get(d, last)
        days[d] = last
        d += timedelta(days=1)
    return days


def analyze(transactions: list[Transaction], policy: Policy, employer: str | None = None) -> BankAnalytics:
    """Aggregate a statement into `BankAnalytics` (thresholds from `policy.banking`)."""
    if not transactions:
        return BankAnalytics(notes=["No bank-statement transactions available."])
    bcfg = policy.section("banking")
    txns = sorted(transactions, key=lambda t: t.date)
    first, last = txns[0].date, txns[-1].date
    months_covered = round(((last - first).days + 1) / 30.44, 1)

    # ------------------------------------------------------------- monthly aggregates
    by_month: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_month[_month(t.date)].append(t)
    daily = _daily_balances(txns)
    monthly: list[dict[str, Any]] = []
    for m in sorted(by_month):
        items = by_month[m]
        credits = sum(t.amount for t in items if t.amount > 0)
        debits = -sum(t.amount for t in items if t.amount < 0)
        mdays = [v for d, v in daily.items() if _month(d) == m]
        closing = mdays[-1] if mdays else (items[-1].balance or 0.0)
        monthly.append({
            "month": m, "credits": round(credits, 2), "debits": round(debits, 2),
            "net": round(credits - debits, 2), "closing": round(closing, 2),
            "avg_balance": round(statistics.fmean(mdays), 2) if mdays else round(closing, 2),
            "txn_count": len(items),
        })
    n_months = max(len(monthly), 1)
    total_credits = sum(t.amount for t in txns if t.amount > 0)
    total_debits = -sum(t.amount for t in txns if t.amount < 0)
    amb = statistics.fmean(m["avg_balance"] for m in monthly)
    balances = list(daily.values()) or [t.balance for t in txns if t.balance is not None] or [0.0]
    notes: list[str] = []

    # ------------------------------------------------------------- salary
    sal = [t for t in txns if is_salary(t, employer)]
    if not sal:
        # fallback: recurring NEFT/IMPS credit of similar amount in >= 3 months
        groups: dict[int, list[Transaction]] = defaultdict(list)
        for t in txns:
            if t.amount > 10000 and TRANSFER_HINT_RE.search(t.description) and not is_cash_deposit(t):
                groups[int(round(t.amount, -3))].append(t)
        best = max(groups.values(), key=lambda g: (len({_month(x.date) for x in g}), sum(x.amount for x in g)), default=[])
        if len({_month(x.date) for x in best}) >= 3:
            sal = best
            notes.append("Salary inferred from a recurring transfer credit (no SALARY keyword).")
    sal_by_month: dict[str, float] = defaultdict(float)
    sal_date: dict[str, date] = {}
    for t in sal:
        sal_by_month[_month(t.date)] += t.amount
        sal_date.setdefault(_month(t.date), t.date)
    salary_credits = [
        {"month": m, "amount": round(a, 2), "date": sal_date[m].isoformat()} for m, a in sorted(sal_by_month.items())
    ]
    avg_salary = statistics.fmean(sal_by_month.values()) if sal_by_month else 0.0
    regularity = 0.0
    if sal_by_month:
        denom = min(n_months, max(1, round(months_covered)))
        share = min(1.0, len(sal_by_month) / denom)
        cov = statistics.pstdev(sal_by_month.values()) / avg_salary if avg_salary and len(sal_by_month) > 1 else 0.0
        regularity = round(max(0.0, min(1.0, share * (1 - min(cov, 1.0)))), 3)

    # ------------------------------------------------------------- EMIs
    emi_groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        if is_emi_debit(t):
            emi_groups[_lender_key(t.description)].append(t)
    detected: list[dict[str, Any]] = []
    for lender, items in emi_groups.items():
        months = {_month(t.date) for t in items}
        explicit = any(_is(t, "EMI") for t in items)
        if len(months) >= 2 or explicit:
            amt = statistics.median(-t.amount for t in items)
            detected.append({"lender": lender, "amount": round(amt, 2), "months": len(months)})
    detected.sort(key=lambda d: -d["amount"])
    total_emi = round(sum(d["amount"] for d in detected), 2)

    # ------------------------------------------------------------- bounces
    bounce_list = [t for t in txns if is_bounce(t)]
    bounce_details = [{"date": t.date.isoformat(), "description": t.description, "amount": t.amount} for t in bounce_list]

    # ------------------------------------------------------------- cash deposits
    cash = [t for t in txns if is_cash_deposit(t)]
    cash_total = sum(t.amount for t in cash)
    credit_amounts = [t.amount for t in txns if t.amount > 0]
    median_credit = statistics.median(credit_amounts) if credit_amounts else 0.0
    mult = float(bcfg.get("cash_deposit_spike_multiple", 3.0))
    spikes: list[dict[str, Any]] = [
        {"date": t.date.isoformat(), "amount": t.amount, "description": t.description,
         "multiple_of_median_credit": round(t.amount / median_credit, 1) if median_credit else None}
        for t in cash if median_credit and t.amount > mult * median_credit
    ]

    # ------------------------------------------------------------- high-risk merchants
    kws = list(bcfg.get("high_risk_merchant_keywords", []))
    hr: dict[str, dict[str, Any]] = {}
    for t in txns:
        if t.amount < 0 or _is(t, "GAMBLING"):
            kw = high_risk_keyword(t.description, kws) or ("gambling" if _is(t, "GAMBLING") else None)
            if kw and t.amount < 0:
                e = hr.setdefault(kw, {"merchant": kw, "count": 0, "amount": 0.0, "examples": []})
                e["count"] += 1
                e["amount"] = round(e["amount"] - t.amount, 2)
                if len(e["examples"]) < 3:
                    e["examples"].append(t.description)
    hr_total = sum(e["amount"] for e in hr.values())

    # ------------------------------------------------------------- tamper heuristics
    nonzero = [t for t in txns if abs(t.amount) >= 1000]
    round_share = (sum(1 for t in nonzero if abs(t.amount) % 1000 == 0) / len(nonzero)) if nonzero else 0.0
    keys = [(t.date, t.description.strip().upper(), t.amount, t.balance) for t in txns]
    dup_share = 1 - len(set(keys)) / len(keys)

    # ------------------------------------------------------------- income estimate
    if avg_salary > 0:
        income_estimate = avg_salary
    else:
        # median monthly credits excluding cash spikes and reversals
        spike_amt: dict[str, float] = defaultdict(float)
        for s in spikes:
            spike_amt[str(s["date"])[:7]] += float(s["amount"])
        clean = [m["credits"] - spike_amt.get(m["month"], 0.0) for m in monthly]
        income_estimate = statistics.median(clean) if clean else 0.0

    if months_covered < float(bcfg.get("min_months_statement", 6)) - 0.5:
        notes.append(f"Statement covers only {months_covered} months.")
    if total_emi:
        notes.append(f"{len(detected)} recurring loan EMI(s) detected in the statement.")

    return BankAnalytics(
        months_covered=months_covered,
        avg_monthly_balance=round(amb, 2),
        min_balance=round(min(balances), 2),
        avg_monthly_credits=round(total_credits / n_months, 2),
        avg_monthly_debits=round(total_debits / n_months, 2),
        salary_credits=salary_credits,
        avg_salary_credit=round(avg_salary, 2),
        salary_regularity=regularity,
        detected_emis=detected,
        total_detected_emi=total_emi,
        bounces=len(bounce_list),
        bounce_details=bounce_details,
        cash_deposit_spikes=spikes,
        high_risk_merchants=sorted(hr.values(), key=lambda e: -e["amount"]),
        monthly=monthly,
        income_estimate=round(income_estimate, 2),
        notes=notes,
        total_credits=round(total_credits, 2),
        total_debits=round(total_debits, 2),
        cash_deposit_total=round(cash_total, 2),
        cash_deposit_share=round(cash_total / total_credits, 4) if total_credits else 0.0,
        high_risk_debit_share=round(hr_total / total_debits, 4) if total_debits else 0.0,
        round_number_share=round(round_share, 4),
        duplicate_txn_share=round(dup_share, 4),
        latest_balance=round(balances[-1], 2),
    )
