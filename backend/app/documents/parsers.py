"""Per-document-type field parsers.

All parsers take *layout text* (PDF text layer in pypdf layout mode, or OCR lines rebuilt by
``ocr.layout_lines``) and are written to survive common OCR noise: dropped spaces
(``NetPay``), stray punctuation (``Net:Pay``), full-width colons, O/0 and l/1 confusions in numbers.
Full PAN numbers are returned only under ``_pan_full`` (transient, for cross-checks inside the
pipeline); the pipeline masks before anything is stored.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from app.schemas import Transaction

# ----------------------------------------------------------------------------- normalisation
_TRANS = str.maketrans({"：": ":", "·": " ", "，": ",", "–": "-", "—": "-", "₹": " Rs ", " ": " "})
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                      "nov", "dec"], start=1)}


def normalize(text: str) -> str:
    t = (text or "").translate(_TRANS)
    return re.sub(r"(?<=[a-z])'(?=[a-z]{2})", "", t)  # OCR apostrophes inside words: addre'ss


def lines_of(text: str) -> list[str]:
    return [ln.rstrip() for ln in normalize(text).splitlines()]


def lbl(label: str) -> str:
    """Regex for a label whose words may be glued or separated by OCR junk: 'Net Pay' -> N\\W*e...?"""
    words = label.split()
    return r"[\s.:'’`]*".join(re.escape(w) for w in words)


_NUM_FIX = str.maketrans("OoIl;", "0011,", " ")
_SEP = r"[\s.'’`\"]*[:;\-]+\s*"
_AMT = r"(-?\(?\d[\dOoIl,\. ]*\d(?:\.\d{1,2})?\)?)"


def parse_amount(s: str | None) -> float | None:
    """'1,45,000.00' / '1.45.000,00' / 'Rs. 62,00,000/-' / '1,45,O00.00' -> float."""
    if s is None:
        return None
    t = str(s).strip()
    t = re.sub(r"(?i)rs\.?|inr|/-", "", t)
    t = t.translate(_NUM_FIX)
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("-()")
    if not re.search(r"\d", t):
        return None
    m = re.match(r"^(.*?)[\.,](\d{2})$", t)
    if m and re.sub(r"[\.,]", "", m.group(1)).isdigit():
        whole, frac = re.sub(r"[\.,]", "", m.group(1)), m.group(2)
        val = float(f"{whole or 0}.{frac}")
    else:
        digits = re.sub(r"[\.,]", "", t)
        if not digits.isdigit():
            return None
        val = float(digits)
    return -val if neg else val


def money_after(text: str, label: str, window: int = 400, min_value: float = 1.0) -> float | None:
    """First money value following ``label`` on the same line."""
    t = normalize(text)
    for m in re.finditer(lbl(label), t, re.I):
        tail = t[m.end(): m.end() + window].split("\n")[0]
        for am in re.finditer(r"(?:Rs\.?\s*)?(\d[\dOo,\.;]*\d)", tail):
            v = parse_amount(am.group(1))
            if v is not None and v >= min_value and ("," in am.group(1) or "." in am.group(1) or v >= 100):
                return v
    return None


def parse_date(s: str) -> date | None:
    s = s.strip().replace(" ", "")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d-%b-%y", "%d%b%Y",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


DATE_RE = r"(\d{2}[/\-.]\d{2}[/\-.]\d{2,4}|\d{2}-[A-Za-z]{3}-\d{2,4})"


def value_after(text: str, label: str) -> str | None:
    """Value after 'Label :' on the same line, cut at the next 2+-space column gap."""
    for ln in lines_of(text):
        m = re.search(lbl(label) + _SEP + r"(.+)", ln, re.I)
        if m:
            v = re.split(r"\s{2,}", m.group(1).strip())[0].strip(" :.")
            if v:
                return v
    return None


def value_block(text: str, label: str, max_lines: int = 3) -> str | None:
    """Like value_after, but also joins indented continuation lines (wrapped paragraphs)."""
    ls = lines_of(text)
    for i, ln in enumerate(ls):
        m = re.search(lbl(label) + _SEP + r"(.+)", ln, re.I)
        if not m:
            continue
        parts = [m.group(1).strip()]
        col = m.start(1)
        for nxt in ls[i + 1: i + 1 + max_lines]:
            if not nxt.strip():
                break
            indent = len(nxt) - len(nxt.lstrip())
            if indent < max(col - 12, 8) or re.match(r"^\s*[A-Z][\w /().'&-]{2,40}\s*:", nxt):
                break
            parts.append(nxt.strip())
        return re.sub(r"\s+", " ", " ".join(parts)).strip(" :")
    return None


def next_line_after(text: str, label: str) -> str | None:
    """Card layouts: the value sits on the line *below* the label."""
    ls = [ln for ln in lines_of(text) if ln.strip()]
    for i, ln in enumerate(ls):
        if re.fullmatch(r"\s*" + lbl(label) + r"\s*[:.]?\s*", ln, re.I) and i + 1 < len(ls):
            return re.split(r"\s{2,}", ls[i + 1].strip())[0]
    return None


def clean_name(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"[.:](?=[A-Za-z])", " ", s)
    s = re.sub(r"[^A-Za-z .&']", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or None


# ----------------------------------------------------------------------------- PAN / Aadhaar
PAN_RE = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{5}[0-9OISBZl]{4}[A-Z0-9])(?![A-Z0-9])")


def find_pan(text: str) -> str | None:
    """Find a PAN, repairing OCR digit/letter confusions. Returns the full value (mask before storing)."""
    to_alpha = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"})
    to_digit = str.maketrans({"O": "0", "I": "1", "l": "1", "S": "5", "B": "8", "Z": "2"})
    for m in PAN_RE.finditer(normalize(text).upper()):
        tok = m.group(1)
        fixed = tok[:5].translate(to_alpha) + tok[5:9].translate(to_digit) + tok[9].translate(to_alpha)
        if re.fullmatch(r"[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]", fixed) and sum(c.isalpha() for c in tok[:5]) >= 4:
            return fixed
    return None


def parse_pan_card(text: str) -> dict[str, Any]:
    name = next_line_after(text, "Name")
    father = next_line_after(text, "Father's Name") or next_line_after(text, "Fathers Name")
    dob_s = next_line_after(text, "Date of Birth")
    dob = None
    m = re.search(r"(\d{2}[/\-.]\d{2}[/\-.]\d{4})", dob_s or "") or re.search(r"(\d{2}/\d{2}/\d{4})", normalize(text))
    if m:
        dob = parse_date(m.group(1))
    return {"name": clean_name(name), "father_name": clean_name(father), "dob": dob, "_pan_full": find_pan(text)}


def parse_aadhaar(text: str) -> dict[str, Any]:
    t = normalize(text)
    out: dict[str, Any] = {}
    m = re.search(r"(?:D[O0]B|Date\s*of\s*Birth|Year\s*of\s*Birth)[\s:.]*(\d{2}[/\-.]\d{2}[/\-.]\d{4})", t, re.I)
    out["dob"] = parse_date(m.group(1)) if m else None
    ls = [ln.strip() for ln in lines_of(t) if ln.strip()]
    name = None
    for i, ln in enumerate(ls):
        if re.search(r"(?:D[O0]B|Date\s*of\s*Birth)", ln, re.I) and i > 0:
            cand = re.split(r"\s{2,}", ls[i - 1])[-1]
            if not re.search(r"(?i)government|india|photo", cand):
                name = cand
            break
    out["name"] = clean_name(name)
    g = re.search(r"\b(MALE|FEMALE|TRANSGENDER)\b", t, re.I)
    out["gender"] = {"MALE": "M", "FEMALE": "F"}.get(g.group(1).upper(), "O") if g else None
    masked = re.search(r"[X×xK]{4}\s?[X×xK]{4}\s?(\d{4})", t)
    full = re.search(r"(?<!\d)(\d{4})\s?(\d{4})\s?(\d{4})(?!\d)", t)
    out["aadhaar_last4"] = masked.group(1) if masked else (full.group(3) if full else None)
    out["aadhaar_was_masked_on_doc"] = bool(masked) and not full
    addr = None
    for i, ln in enumerate(ls):
        if re.match(r"(?i)address\s*:?", ln):
            rest = re.sub(r"(?i)^address\s*:?\s*", "", ln)
            block = [rest] if rest else []
            for nxt in ls[i + 1: i + 6]:
                if re.search(r"[X×]{4}|aadhaar|masked|specimen", nxt, re.I):
                    break
                block.append(nxt)
                if re.search(r"\b\d{6}\b", nxt):
                    break
            addr = re.sub(r"\s+", " ", " ".join(block)).strip()
            addr = re.sub(r"^(?:[SDWC]\s*/\s*O|C/O)\s*:?\s*[^,]+,\s*", "", addr, flags=re.I)
            break
    out["address"] = addr
    pin = re.search(r"\b(\d{6})\b", addr or "")
    out["pincode"] = pin.group(1) if pin else None
    return out


# ----------------------------------------------------------------------------- income docs
def parse_month(text: str) -> str | None:
    t = normalize(text)
    m = re.search(r"(?i)month\W*of\W*([A-Za-z]{3,9})\W*(\d{4})", t) or \
        re.search(r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\W*(\d{4})", t)
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].lower())
    return f"{m.group(2)}-{mon:02d}" if mon else None


def first_heading(text: str) -> str | None:
    for ln in lines_of(text):
        s = ln.strip()
        if len(s) >= 4 and re.search(r"[A-Za-z]{3}", s):
            return re.split(r"\s{2,}", s)[0]
    return None


def parse_salary_slip(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "employer": first_heading(text),
        "month": parse_month(text),
        "employee_name": clean_name(value_after(text, "Employee Name") or value_after(text, "Name of Employee")),
        "gross": money_after(text, "Gross Earnings") or money_after(text, "Gross Salary") or money_after(text, "Total Earnings"),
        "total_deductions": money_after(text, "Total Deductions"),
        "net_pay": None,
        "basic": money_after(text, "Basic Salary") or money_after(text, "Basic Pay") or money_after(text, "Basic"),
        "pf": money_after(text, "Provident Fund") or money_after(text, "NPS"),
        "pt": money_after(text, "Professional Tax", min_value=0.0),
        "tds": money_after(text, "Income Tax", min_value=0.0),
        "_pan_full": find_pan(text),
    }
    for m in re.finditer(r"(?i)net\W*pay(?!\W*\(?\W*in\W*words)|net\W*salary|take\W*home", normalize(text)):
        tail = normalize(text)[m.end(): m.end() + 400].split("\n")[0]
        am = re.search(r"(\d[\dOo,\.;]*\d)", tail)
        if am:
            v = parse_amount(am.group(1))
            if v and v >= 1000:
                out["net_pay"] = v
                break
    if out["net_pay"] is None and out["gross"] and out["total_deductions"] is not None:
        out["net_pay"] = round(out["gross"] - out["total_deductions"], 2)
    amounts = [parse_amount(a) for a in re.findall(r"(?<![\d,])\d{1,3}(?:,\d{2,3})*\.\d{2}(?!\d)", normalize(text))]
    out["_amounts"] = [a for a in amounts if a]
    return out


def _two_col(text: str, label: str) -> tuple[str | None, str | None]:
    """Form 16 header: 'Name and address of the Employer:   Name of the Employee:' then values below."""
    ls = [ln for ln in lines_of(text)]
    for i, ln in enumerate(ls):
        if re.search(lbl(label), ln, re.I):
            for nxt in ls[i + 1: i + 3]:
                if nxt.strip():
                    cols = re.split(r"\s{3,}", nxt.strip())
                    return cols[0], (cols[1] if len(cols) > 1 else None)
    return None, None


def parse_form16(text: str) -> dict[str, Any]:
    employer, employee = _two_col(text, "Name and address of the Employer")
    t = normalize(text)
    ay = re.search(r"(?i)assessment\W*year\W*(\d{4}\s*-\s*\d{2,4})", t)
    gross = money_after(text, "Total amount of salary received") or money_after(text, "(d) Total") \
        or money_after(text, "Gross Salary")
    return {
        "employer": clean_name(employer) if employer else None,
        "employee_name": clean_name(employee),
        "ay": ay.group(1).replace(" ", "") if ay else None,
        "gross_salary": gross,
        "taxable_income": money_after(text, "Total taxable income"),
        "tax": money_after(text, "Net tax payable", min_value=0.0),
        "tan": (re.search(r"\b([A-Z]{4}\d{5}[A-Z])\b", t) or [None, None])[1],
        "_pan_full": find_pan(re.sub(r"\b[A-Z]{4}\d{5}[A-Z]\b", " ", t)),
    }


def parse_itr(text: str) -> dict[str, Any]:
    t = normalize(text)
    ay = re.search(r"(?i)assessment\W*year\W*(\d{4}\s*-\s*\d{2,4})", t) or \
        re.search(r"(?i)year\W*(20\d{2}\s*-\s*\d{2})\b", t)
    form = re.search(r"\bITR\s*-?\s*([1-7])\b", t)
    total = None
    for ln in lines_of(t):
        if re.search(r"(?i)\btota[il1]\W*income\b", ln) and not re.search(r"(?i)gross|taxable", ln):
            am = re.findall(r"(\d[\d,.;]*\d)\W*$", ln.strip())
            if am:
                total = parse_amount(am[-1])
                break
    filed = re.search(r"(?i)date\W*of\W*filing\W*" + DATE_RE, t)
    return {
        "name": clean_name(value_after(text, "Name")),
        "ay": ay.group(1).replace(" ", "") if ay else None,
        "form": f"ITR-{form.group(1)}" if form else None,
        "total_income": total,
        "gross_total_income": money_after(text, "Gross Total Income"),
        "tax_paid": money_after(text, "Taxes Paid", min_value=0.0),
        "filing_date": parse_date(filed.group(1)) if filed else None,
        "_pan_full": find_pan(text),
    }


# ----------------------------------------------------------------------------- bank statement
_ROW_DATE = re.compile(r"^\s*(\d{2}[/\-]\d{2}[/\-]\d{2,4}|\d{2}-[A-Za-z]{3}-\d{2,4})\s+(.*)$")
_MONEY_TAIL = re.compile(r"(-?\d{1,3}(?:,\d{2,3})*\.\d{2})(?:\s*(Cr|Dr|CR|DR))?")

CATEGORY_RULES: list[tuple[str, str, str]] = [
    # (category, sign: '+', '-' or '*', regex)
    ("BOUNCE", "*", r"ECS\s*RTN|NACH\s*RTN|ACH\s*RTN|RETURN|BOUNCE|DISHONOU?R|INSUFF"),
    ("GAMBLING", "*", r"DREAM11|RUMMY|\bBET\b|CASINO|POKER|LOTTERY|TEEN\s*PATTI|1XBET|\bSTAKE\b|\bMPL\b"),
    ("CRYPTO", "*", r"CRYPTO|BINANCE|WAZIRX|COINDCX"),
    ("SALARY", "+", r"SALARY|\bSAL\b|PAYROLL"),
    ("EMI", "-", r"\bEMI\b|LOAN"),
    ("CASH_DEPOSIT", "+", r"CASH\s*DEP|\bCDM\b|BY\s*CASH"),
    ("CASH_WITHDRAWAL", "-", r"ATM\s*WDL|CASH\s*WDL|\bATW\b|NWD"),
    ("INTEREST", "+", r"INT\.?\s*PD|INTEREST"),
    ("TAX", "-", r"CBDT|ITNS|GST\s*PMT|TDS"),
    ("INVESTMENT", "-", r"\bSIP\b|MUTUAL|\bMF\b|BROKING|SECURITIES|TRADING"),
    ("INSURANCE", "-", r"LIC\b|INSURANCE|PREMIUM"),
    ("UTILITY", "-", r"BILLDESK|ELECTRICITY|BILLPAY|POSTPAID|BROADBAND|GAS\s*BILL|WATER"),
    ("RENT", "-", r"\bRENT\b"),
    ("CARD", "-", r"\bPOS\b|CC\s*BILLPAY|CREDIT\s*CARD"),
    ("BUSINESS_CREDIT", "+", r"SETTLEMENT|INV\s*PMT|PROF\s*FEES|TPA|PATIENT|CLAIMS"),
    ("UPI", "*", r"\bUPI\b"),
    ("TRANSFER_IN", "+", r"NEFT|IMPS|RTGS|TRF|TRANSFER"),
    ("TRANSFER_OUT", "-", r"NEFT|IMPS|RTGS|TRF|TRANSFER|STAFF"),
]


def categorize(description: str, amount: float) -> str:
    d = description.upper()
    for cat, sign, pat in CATEGORY_RULES:
        if (sign == "+" and amount <= 0) or (sign == "-" and amount >= 0):
            continue
        if cat == "SALARY" and "STAFF" in d:
            continue
        if re.search(pat, d):
            return cat
    return "OTHER"


def parse_bank_statement(text: str) -> tuple[dict[str, Any], list[Transaction]]:
    t = normalize(text)
    meta: dict[str, Any] = {
        "bank_name": first_heading(t),
        "account_holder": clean_name(value_after(t, "Account Holder") or value_after(t, "Customer Name")
                                     or value_after(t, "Name")),
        "address": value_block(t, "Address", max_lines=1),
        "account_no": value_after(t, "Account No") or value_after(t, "A/c No"),
        "ifsc": (re.search(r"IFSC\W*([A-Z]{4}0[A-Z0-9]{6})", t) or [None, None])[1],
    }
    per = re.search(r"(?i)period\W*" + DATE_RE + r"\s*(?:to|-)\s*" + DATE_RE, t)
    if per:
        meta["period_start"], meta["period_end"] = parse_date(per.group(1)), parse_date(per.group(2))
    opening = None
    for ln in t.splitlines():
        if re.search(r"(?i)opening\s*balance", ln) and not re.search(r"(?i)summary|count", ln):
            mm = _MONEY_TAIL.findall(ln)
            if mm:
                opening = parse_amount(mm[-1][0])
                break
    meta["opening_balance"] = opening
    txns: list[Transaction] = []
    prev = opening
    for ln in t.splitlines():
        m = _ROW_DATE.match(ln)
        if not m:
            continue
        d = parse_date(m.group(1))
        if d is None:
            continue
        rest = m.group(2)
        monies = list(_MONEY_TAIL.finditer(rest))
        if len(monies) < 2:
            continue
        bal_m, amt_m = monies[-1], monies[-2]
        balance = parse_amount(bal_m.group(1))
        amount = parse_amount(amt_m.group(1))
        if balance is None or amount is None:
            continue
        if bal_m.group(2) and bal_m.group(2).upper() == "DR":
            balance = -balance
        desc_part = rest[: amt_m.start()]
        # drop value date + ref column (layout columns are separated by 2+ spaces)
        cols = [c for c in re.split(r"\s{2,}", desc_part.strip()) if c]
        while cols and (parse_date(cols[-1]) or (re.fullmatch(r"[A-Z0-9]{6,20}", cols[-1]) and re.search(r"\d", cols[-1]))):
            cols.pop()
        desc = " ".join(cols).strip()
        if prev is not None and abs(abs(balance - prev) - amount) < 0.05:
            signed = round(balance - prev, 2)
        elif amt_m.group(2):
            signed = amount if amt_m.group(2).upper() == "CR" else -amount
        else:
            signed = amount if re.search(r"(?i)\bCR\b|/CR/|DEP|CREDIT|SALARY|INT\.PD", desc) else -amount
        prev = balance
        txns.append(Transaction(date=d, description=desc, amount=signed, balance=balance,
                                category=categorize(desc, signed)))
    if txns:
        meta["closing_balance"] = txns[-1].balance
        meta.setdefault("period_start", txns[0].date)
        meta.setdefault("period_end", txns[-1].date)
    return meta, txns


# ----------------------------------------------------------------------------- property docs
def parse_sale_deed(text: str) -> dict[str, Any]:
    t = normalize(text)
    sq = re.sub(r"[^a-z]", "", t.lower())
    deed_type = "TITLE_DEED" if "titledeed" in sq else "AGREEMENT_FOR_SALE" if "agreementforsale" in sq else "SALE_DEED"
    consideration = money_after(t, "Total Consideration") or money_after(t, "consideration of the sum of") \
        or money_after(t, "Consideration")
    reg = re.search(r"(?i)registration\W*no\W*[:\-]?\s*([A-Z][A-Z\-]*-?\d*/\d+/\d{4})", t)
    reg_date = re.search(r"(?i)date\W*of\W*registration\W*[:\-]?\s*" + DATE_RE, t)
    area = re.search(r"(?i)(?:carpet|built[\s-]*up|super)?\W*area\W*[:\-]?\s*([\d,]+(?:\.\d+)?)[\s.'’:]*sq", t)
    enc = value_after(t, "Encumbrance")
    encumbrance = None
    if enc:
        encumbrance = "NIL" if re.search(r"(?i)\bnil\b|free from|none", enc) else enc
    elif re.search(r"(?i)free\s*from\s*all\s*encumbrances", t):
        encumbrance = "NIL"
    return {
        "deed_type": deed_type,
        "property_address": value_block(t, "Property Address"),
        "consideration_value": consideration,
        "registration_no": reg.group(1) if reg else None,
        "registration_date": parse_date(reg_date.group(1)) if reg_date else None,
        "area_sqft": parse_amount(area.group(1)) if area else None,
        "owner": clean_name(value_block(t, "Owner / Purchaser") or value_block(t, "Purchaser")),
        "vendor": clean_name(value_after(t, "Vendor")),
        "encumbrance": encumbrance,
        "sro": value_block(t, "Registering Office", max_lines=1),
    }


def parse_valuation(text: str) -> dict[str, Any]:
    t = normalize(text)
    area = re.search(r"(?i)(?:carpet|built[\s-]*up)?\W*area\W*[:\-]?\s*([\d,]+(?:\.\d+)?)[\s.'’:]*sq", t)
    return {
        "valuer": first_heading(t),
        "owner": clean_name(value_after(t, "Name of the Applicant / Owner") or value_after(t, "Owner")),
        "property_address": value_block(t, "Property Address"),
        "market_value": money_after(t, "Fair Market Value") or money_after(t, "Market Value"),
        "realisable_value": money_after(t, "Realisable Value (90%)") or money_after(t, "Realisable Value"),
        "distress_value": money_after(t, "Distress Value (80%)") or money_after(t, "Distress Value")
        or money_after(t, "Forced Sale Value"),
        "guideline_value": money_after(t, "Ready Reckoner Value") or money_after(t, "Guideline Value"),
        "agreement_value": money_after(t, "Agreement / Purchase Value"),
        "area_sqft": parse_amount(area.group(1)) if area else None,
        "inspection_date": parse_date((re.search(r"(?i)date\W*of\W*inspection\W*" + DATE_RE, t) or [None, ""])[1] or ""),
    }
