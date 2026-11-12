"""Hand-built schema objects for engine / capacity unit tests (no dependency on the docs layer)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.policy.loader import get_policy
from app.schemas import (
    ApplicationForm,
    DocType,
    DocumentBundle,
    DocumentResult,
    EmploymentType,
    Product,
    RiskScore,
    Transaction,
)

AS_OF = date(2026, 11, 12)
STARTED = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
POLICY = get_policy()


def form(**kw: Any) -> ApplicationForm:
    base: dict[str, Any] = dict(
        product=Product.HOME_LOAN, applicant_name="Aarav Kulkarni", dob=date(1992, 5, 10),
        employment_type=EmploymentType.SALARIED, employer_or_business="Zentrix Software Pvt Ltd", years_in_job=4,
        declared_monthly_income=150000, existing_emi=0, bureau_score=780, loan_amount=4500000, tenure_months=240,
        property_value=6200000, property_type="RESIDENTIAL", city="Pune",
    )
    base.update(kw)
    return ApplicationForm(**base)


def statement(
    salary: float = 150000, months: int = 6, emi: float = 0.0, emi_desc: str = "NACH DR HDFC BANK CAR LOAN EMI",
    extra: list[tuple[int, int, str, float]] | None = None, start_balance: float = 250000.0,
    salary_desc: str = "NEFT CR SALARY ZENTRIX SOFTWARE",
) -> list[Transaction]:
    """`months` months ending Oct-2026 with salary on the 1st and realistic non-round spends.
    `extra`: (month_index, day, description, amount)."""
    txns: list[tuple[date, str, float]] = []
    for i in range(months):
        y, m = 2026, 10 - months + 1 + i
        while m <= 0:
            m += 12
            y -= 1
        txns.append((date(y, m, 1), salary_desc, salary))
        txns.append((date(y, m, 3), "UPI/SWIGGY/ORDER 4471", -1834.50 - 13 * i))
        txns.append((date(y, m, 5), "ACH D- TATA POWER BILL", -3271.20 + 7 * i))
        txns.append((date(y, m, 8), "UPI/BIGBASKET GROCERY", -6743.80 - 11 * i))
        txns.append((date(y, m, 12), "POS AMAZON RETAIL", -4519.35 + 3 * i))
        txns.append((date(y, m, 15), "IMPS RENT TO LANDLORD", -28417.00))
        txns.append((date(y, m, 20), "UPI/ZOMATO", -1288.40 + 5 * i))
        txns.append((date(y, m, 25), "ATM WDL CASH", -5000.0))
        if emi:
            txns.append((date(y, m, 7), emi_desc, -emi))
        for (mi, day, desc, amt) in extra or []:
            if mi == i:
                txns.append((date(y, m, day), desc, amt))
    txns.sort(key=lambda t: t[0])
    bal = start_balance
    out = []
    for d, desc, amt in txns:
        bal += amt
        out.append(Transaction(date=d, description=desc, amount=amt, balance=round(bal, 2)))
    return out


def doc(doc_type: DocType, i: int = 0, **kw: Any) -> DocumentResult:
    return DocumentResult(id=f"{doc_type.value.lower()}-{i}", filename=f"{doc_type.value.lower()}_{i}.pdf",
                          doc_type=doc_type, sha256=f"sha-{doc_type.value}-{i}", **kw)


def bundle(salaried: bool = True, net: float = 150000, **kw: Any) -> DocumentBundle:
    docs = [doc(DocType.PAN), doc(DocType.AADHAAR), doc(DocType.BANK_STATEMENT), doc(DocType.SALE_DEED),
            doc(DocType.VALUATION_REPORT)]
    if salaried:
        docs += [doc(DocType.SALARY_SLIP, i) for i in range(3)] + [doc(DocType.FORM16)]
    else:
        docs += [doc(DocType.ITR)]
    base: dict[str, Any] = dict(
        documents=docs,
        salary_slips=[{"month": f"2026-0{7 + i}", "gross": net * 1.3, "net": net, "employer": "Zentrix"} for i in range(3)]
        if salaried else [],
        identity={"name": "Aarav Kulkarni", "dob": "1992-05-10", "pan_masked": "XXXXX1234F", "aadhaar_masked": "XXXX XXXX 4321"},
        property={"market_value": 6200000, "consideration_value": 6200000, "encumbrance": "NIL", "owner": "Aarav Kulkarni"},
    )
    base.update(kw)
    return DocumentBundle(**base)


def risk(grade: str = "A", pd: float = 0.015) -> RiskScore:
    bands = {"A": "Low", "B": "Moderate", "C": "Elevated", "D": "High", "E": "Very high"}
    return RiskScore(pd=pd, score=780, grade=grade, band=bands[grade], model_version="test")  # type: ignore[arg-type]
