"""Generate the 12 synthetic FinPilot HomeLoan personas and their Indian-format documents.

Output: ``<repo>/data/personas/<pid>/`` with
  application.json  ApplicationForm + {"persona": {id, title, segment, story, expected_outcome}}
  expected.json     expected outcome + key facts per document (used by tests)
  pan_card.png, aadhaar_card.png (masked Aadhaar, as UIDAI recommends)
  salary_slip_YYYY-MM.pdf x3 + form16_ay2026-27.pdf (salaried) | itr_v_ayYYYY-YY.pdf x2 (self-employed)
  bank_statement.pdf, agreement_for_sale.pdf | sale_deed.pdf | title_deed.pdf, valuation_report.pdf
Some documents per persona are emitted as PNG "scans" (rasterised, rotated, noisy) to exercise OCR.

Everything is fictitious and deterministic (seeded). Requires reportlab, Pillow, pypdf and poppler's
``pdftoppm`` (for the scanned PNGs).

Usage (from backend/):  python scripts/generate_personas.py [--out DIR] [--only p01,p07] [--zip]
``--zip`` also writes ``<out>/<pid>_upload_pack.zip`` with the documents (no json) for upload demos.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import shutil
import subprocess
import sys
import tempfile
import zipfile
import zlib
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import reportlab
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persona_specs import PERSONAS, Persona

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "data" / "personas"
APP_DATE = date(2026, 11, 10)
SLIP_MONTHS = [(2026, 8), (2026, 9), (2026, 10)]
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
W, H = A4
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


# =========================================================================== formatting helpers
def inr(x: float, dec: int = 2) -> str:
    """Indian digit grouping: 1234567.5 -> '12,34,567.50'."""
    neg = x < 0
    x = abs(x)
    whole = round(x * 100) // 100 if dec else round(x)
    frac = round(x * 100) % 100
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join([*parts, tail])
    out = f"{s}.{frac:02d}" if dec else s
    return f"-{out}" if neg else out


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def words(n: float) -> str:
    """Indian-system words: 6200000 -> 'Sixty Two Lakh'."""
    n = round(n)
    if n == 0:
        return "Zero"
    parts = []
    for div, name in ((10 ** 7, "Crore"), (10 ** 5, "Lakh"), (1000, "Thousand"), (100, "Hundred")):
        if n >= div:
            q = n // div
            parts.append(f"{words(q) if q >= 100 else _two(q)} {name}")
            n %= div
    if n:
        parts.append(_two(n))
    return " ".join(parts)


def dmy(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def dmon(d: date) -> str:
    return d.strftime("%d-%b-%Y")


def pdf_date(dt: datetime) -> str:
    return dt.strftime("D:%Y%m%d%H%M%S+05'30'")


def last_working_day(y: int, m: int) -> date:
    d = date(y, m, monthrange(y, m)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def tax_new_regime(taxable: float) -> float:
    """FY 2025-26 new-regime slab tax incl. s.87A rebate up to Rs 12 lakh and 4% cess."""
    slabs = [(400000, 0.0), (800000, 0.05), (1200000, 0.10), (1600000, 0.15), (2000000, 0.20),
             (2400000, 0.25), (float("inf"), 0.30)]
    tax, prev = 0.0, 0.0
    for upper, rate in slabs:
        if taxable > prev:
            tax += (min(taxable, upper) - prev) * rate
        prev = upper
    if taxable <= 1200000:
        tax = 0.0
    return round(tax * 1.04)


# =========================================================================== pdf drawing helper
class Doc:
    """Tiny wrapper over a reportlab canvas (A4 portrait, points, origin bottom-left)."""

    def __init__(self, title: str) -> None:
        self.buf = io.BytesIO()
        self.c = rl_canvas.Canvas(self.buf, pagesize=A4, invariant=1)
        self.c.setTitle(title)
        self.font = "Helvetica"

    def text(self, x: float, y: float, s: str, size: float = 9, font: str | None = None,
             align: str = "l", color: tuple[float, float, float] = (0, 0, 0)) -> None:
        c = self.c
        c.setFillColorRGB(*color)
        c.setFont(font or self.font, size)
        if align == "r":
            c.drawRightString(x, y, s)
        elif align == "c":
            c.drawCentredString(x, y, s)
        else:
            c.drawString(x, y, s)
        c.setFillColorRGB(0, 0, 0)

    def bold(self, x: float, y: float, s: str, size: float = 9, align: str = "l") -> None:
        self.text(x, y, s, size, "Helvetica-Bold", align)

    def line(self, x1: float, y1: float, x2: float, y2: float, w: float = 0.6) -> None:
        self.c.setLineWidth(w)
        self.c.line(x1, y1, x2, y2)

    def rect(self, x: float, y: float, w: float, h: float, fill: tuple[float, float, float] | None = None,
             stroke: bool = True) -> None:
        if fill:
            self.c.setFillColorRGB(*fill)
        self.c.rect(x, y, w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)
        self.c.setFillColorRGB(0, 0, 0)

    def para(self, x: float, y: float, s: str, width: float, size: float = 9, leading: float = 12.5,
             font: str | None = None) -> float:
        """Greedy word-wrap; returns the y below the paragraph."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        f = font or self.font
        line = ""
        for word in s.split():
            trial = f"{line} {word}".strip()
            if stringWidth(trial, f, size) > width and line:
                self.text(x, y, line, size, f)
                y -= leading
                line = word
            else:
                line = trial
        if line:
            self.text(x, y, line, size, f)
            y -= leading
        return y

    def footer(self, s: str) -> None:
        self.text(W / 2, 22, s, 6.5, align="c", color=(0.4, 0.4, 0.4))

    def page(self) -> None:
        self.c.showPage()

    def finish(self, producer: str, creator: str, created: datetime, modified: datetime | None = None,
               author: str = "") -> bytes:
        self.c.save()
        reader = PdfReader(io.BytesIO(self.buf.getvalue()))
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({
            "/Producer": producer, "/Creator": creator, "/Author": author,
            "/CreationDate": pdf_date(created), "/ModDate": pdf_date(modified or created),
        })
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()


SYNTH = "SYNTHETIC TEST DOCUMENT - FinPilot HomeLoan hackathon demo - not a real record"


# =========================================================================== salary
def salary_structure(p: Persona) -> dict[str, Any]:
    """Build a realistic monthly pay structure whose net pay ~= p.target_net (non-round figures)."""
    def build(gross: float) -> dict[str, Any]:
        if p.pay_style == "govt":
            basic = round(gross / 1.83)
            da = round(basic * 0.53)
            hra = round(basic * 0.18)
            ta = round(gross - basic - da - hra)
            earn = [("Basic Pay", basic), ("Dearness Allowance (53%)", da), ("House Rent Allowance", hra),
                    ("Transport Allowance", ta)]
            nps = round(0.10 * (basic + da))
            gis = 480
            annual_taxable = 12 * gross - 75000
            tds = round(tax_new_regime(annual_taxable) / 12)
            ded = [("NPS (Employee 10%)", nps), ("Group Insurance (GIS)", gis), ("Professional Tax", p.pt),
                   ("Income Tax (TDS)", tds)]
        else:
            basic = round(gross * 0.45)
            hra = round(basic * 0.40)
            conv = 1600
            lta = round(gross * 0.05)
            special = round(gross - basic - hra - conv - lta)
            earn = [("Basic Salary", basic), ("House Rent Allowance", hra), ("Conveyance Allowance", conv),
                    ("Leave Travel Allowance", lta), ("Special Allowance", special)]
            pf = round(0.12 * basic)
            tds = round(tax_new_regime(12 * gross - 75000) / 12)
            ded = [("Provident Fund (PF)", pf), ("Professional Tax (PT)", p.pt), ("Income Tax (TDS)", tds)]
            if p.pid in ("p01", "p11"):
                ded.append(("Group Health Insurance", 1240 if p.pid == "p01" else 2310))
        earn = [(k, float(v)) for k, v in earn]
        ded = [(k, float(v)) for k, v in ded if v or k.startswith("Professional")]
        g = sum(v for _, v in earn)
        td = sum(v for _, v in ded)
        return {"earnings": earn, "deductions": ded, "gross": g, "total_deductions": td, "net": g - td}

    lo, hi = p.target_net, p.target_net * 2.2
    for _ in range(60):
        mid = (lo + hi) / 2
        if build(mid)["net"] < p.target_net:
            lo = mid
        else:
            hi = mid
    s = build(round(hi) + 17)
    return s


def forged_structure(p: Persona, genuine: dict[str, Any]) -> dict[str, Any]:
    """p07: earnings + net retyped as round numbers; deductions left as in the genuine slip."""
    gross = float(p.extra["forged_gross"])
    earn = [("Basic Salary", 100000.0), ("House Rent Allowance", 50000.0), ("Conveyance Allowance", 4000.0),
            ("Leave Travel Allowance", 10000.0), ("Special Allowance", 36000.0)]
    return {"earnings": earn, "deductions": genuine["deductions"], "gross": gross,
            "total_deductions": genuine["total_deductions"], "net": float(p.extra["forged_net"]),
            "forged_keys": {k for k, _ in earn} | {"gross", "net"}}


def render_salary_slip(p: Persona, y: int, m: int, s: dict[str, Any]) -> bytes:
    o = p.org
    d = Doc(f"Payslip {MONTHS[m - 1]} {y}")
    forged = s.get("forged_keys", set())
    ff = "Times-Roman"  # forger's font

    d.rect(30, 760, W - 60, 56, fill=(0.93, 0.95, 0.99))
    d.bold(45, 795, o.name.upper(), 15)
    d.text(45, 780, o.address, 8.5)
    if o.cin:
        d.text(45, 768, f"CIN: {o.cin}", 7.5)
    d.bold(W / 2, 735, f"PAYSLIP FOR THE MONTH OF {MONTHS[m - 1].upper()} {y}", 11, "c")
    rows = [("Employee Name", p.name_on_pan.title(), "Employee ID", p.emp_id),
            ("Designation", p.designation, "Date of Joining", dmy(p.doj or date(2020, 1, 1))),
            ("PAN", p.pan, "Bank A/c No", "XXXXXXXX" + p.bank.account_no[-4:]),
            ("Bank Name", p.bank.name, "Pay Days", f"{monthrange(y, m)[1]}"),
            ("Location", p.city, "Pay Date", dmy(last_working_day(y, m)))]
    yy = 712
    for a, b, c2, dd in rows:
        d.text(40, yy, a, 8.5)
        d.text(130, yy, f": {b}", 8.5)
        d.text(330, yy, c2, 8.5)
        d.text(420, yy, f": {dd}", 8.5)
        yy -= 15
    top = yy - 6
    d.rect(35, top - 20, W - 70, 20, fill=(0.85, 0.88, 0.95))
    d.bold(45, top - 14, "EARNINGS", 9)
    d.bold(285, top - 14, "AMOUNT (Rs.)", 9, "r")
    d.bold(310, top - 14, "DEDUCTIONS", 9)
    d.bold(550, top - 14, "AMOUNT (Rs.)", 9, "r")
    yy = top - 36
    n = max(len(s["earnings"]), len(s["deductions"]))
    for i in range(n):
        if i < len(s["earnings"]):
            k, v = s["earnings"][i]
            d.text(45, yy, k, 8.5)
            if k in forged:
                d.rect(200, yy - 3, 88, 12, fill=(1, 1, 1), stroke=False)
            d.text(285, yy, inr(v), 8.5, ff if k in forged else None, "r")
        if i < len(s["deductions"]):
            k, v = s["deductions"][i]
            d.text(310, yy, k, 8.5)
            d.text(550, yy, inr(v), 8.5, None, "r")
        yy -= 16
    d.line(35, yy + 8, W - 35, yy + 8)
    d.bold(45, yy - 6, "Gross Earnings", 9)
    d.text(285, yy - 6, inr(s["gross"]), 9, ff if "gross" in forged else "Helvetica-Bold", "r")
    d.bold(310, yy - 6, "Total Deductions", 9)
    d.bold(550, yy - 6, inr(s["total_deductions"]), 9, "r")
    d.rect(35, top - 20 - (n + 2) * 16 - 4, W - 70, (n + 2) * 16 + 4)
    yy -= 40
    d.rect(35, yy - 8, W - 70, 24, fill=(0.95, 0.97, 0.93))
    d.bold(45, yy, "NET PAY", 11)
    d.text(550, yy, f"Rs. {inr(s['net'])}", 11, ff if "net" in forged else "Helvetica-Bold", "r")
    yy -= 26
    d.text(45, yy, f"Net Pay (in words): Rupees {words(s['net'])} Only", 8.5)
    yy -= 22
    pf_line = "PF/UAN: XXXXXXXX" + str(zlib.crc32(p.pid.encode()) % 9000 + 1000) if p.pay_style != "govt" else "PRAN: XXXXXXXX" + p.emp_id[-4:]
    d.text(45, yy, pf_line, 8)
    d.text(45, yy - 30, "This is a computer-generated payslip and does not require a signature.", 7.5)
    d.footer(SYNTH)
    created = datetime(y, m, last_working_day(y, m).day, 18, 5, 12)
    if p.forged:
        return d.finish("iLovePDF", "iLovePDF", created, datetime(2026, 11, 6, 22, 41, 3))
    return d.finish(f"{o.short.title()} HRMS Payroll (ReportLab PDF Library)", f"{o.short.title()} HRMS", created)


def render_form16(p: Persona, monthly_gross: float) -> tuple[bytes, dict[str, Any]]:
    o = p.org
    gross = round(monthly_gross * 12 * 0.93)
    std = 75000
    pt = p.pt * 12
    income_sal = gross - std - pt
    taxable = income_sal
    tax = tax_new_regime(taxable)
    d = Doc("Form 16 Part B")
    d.bold(W / 2, 800, "FORM NO. 16", 14, "c")
    d.bold(W / 2, 784, "PART B (Annexure)", 11, "c")
    d.text(W / 2, 770, "[See rule 31(1)(a)] Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary", 7.5, align="c")
    d.rect(35, 690, W - 70, 70)
    d.text(42, 746, "Name and address of the Employer:", 8.5)
    d.bold(42, 733, o.name, 9.5)
    d.text(42, 720, o.address, 8.5)
    d.text(320, 746, "Name of the Employee:", 8.5)
    d.bold(320, 733, p.name_on_pan, 9.5)
    d.text(320, 720, f"PAN of the Employee: {p.pan}", 8.5)
    d.text(42, 700, f"TAN of the Deductor: {o.tan}", 8.5)
    d.text(320, 700, f"Employee Reference No.: {p.emp_id}", 8.5)
    d.text(42, 672, "Assessment Year: 2026-27", 9)
    d.text(220, 672, "Period with the Employer: 01-Apr-2025 to 31-Mar-2026", 9)
    d.bold(42, 650, "Details of Salary Paid and any other income and tax deducted", 9.5)
    rows = [
        ("1. Gross Salary", ""),
        ("   (a) Salary as per provisions contained in section 17(1)", inr(gross)),
        ("   (b) Value of perquisites under section 17(2)", inr(0)),
        ("   (d) Total", inr(gross)),
        ("2. Less: Allowances to the extent exempt under section 10", inr(0)),
        ("3. Total amount of salary received from current employer", inr(gross)),
        ("4. Less: Deductions under section 16", ""),
        ("   (a) Standard deduction under section 16(ia)", inr(std)),
        ("   (c) Tax on employment under section 16(iii)", inr(pt)),
        ("5. Income chargeable under the head \"Salaries\"", inr(income_sal)),
        ("6. Gross total income", inr(income_sal)),
        ("7. Total taxable income", inr(taxable)),
        ("8. Tax on total income (incl. Health & Education Cess)", inr(tax)),
        ("9. Rebate under section 87A", inr(0)),
        ("10. Net tax payable", inr(tax)),
        ("11. Tax deducted at source (TDS) - total", inr(tax)),
    ]
    yy = 630
    for k, v in rows:
        d.text(45, yy, k, 8.5)
        if v:
            d.text(550, yy, v, 8.5, align="r")
        d.line(40, yy - 4, W - 40, yy - 4, 0.2)
        yy -= 17
    d.text(42, yy - 10, "Tax regime opted: New regime under section 115BAC", 8.5)
    yy = d.para(42, yy - 40,
                f"I, Authorised Signatory of {o.name}, certify that a sum of Rs. {inr(tax)} has been deducted and "
                "deposited to the credit of the Central Government and the information given above is true, "
                "complete and correct.", W - 90, 8.5)
    d.text(42, yy - 14, "Place: " + o.address.split(",")[-1].strip().split(" ")[0] + "    Date: 12-Jun-2026", 8.5)
    d.footer(SYNTH)
    data = d.finish("TRACES Form 16 Generator (ReportLab PDF Library)", "TRACES", datetime(2026, 6, 12, 11, 2, 9))
    return data, {"employer": o.name, "ay": "2026-27", "gross_salary": float(gross),
                  "taxable_income": float(taxable), "tax": float(tax), "employee_name": p.name_on_pan}


def render_itr_v(p: Persona, ay: str, income: float) -> tuple[bytes, dict[str, Any]]:
    form = "ITR-4" if p.pid in ("p04",) else "ITR-3"
    gti = income + 150000
    ded = 150000
    tax = tax_new_regime(income) if income > 1200000 else 0.0
    paid = tax
    fy_end = int(ay[:4])
    filed = date(fy_end, 7, 24 if p.pid != "p03" else 29)
    ack = f"{(zlib.crc32((p.pid + ay).encode()) % 10 ** 6):06d}{filed.strftime('%d%m%y')}{fy_end % 100}9"
    d = Doc(f"ITR-V {ay}")
    d.bold(W / 2, 800, "INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT", 13, "c")
    d.text(W / 2, 786, f"[Where the data of the Return of Income in Form {form} has been transmitted electronically]", 8, align="c")
    d.bold(W - 45, 806, f"Assessment Year {ay}", 10, "r")
    d.rect(35, 640, W - 70, 132)
    kv = [("PAN", p.pan), ("Name", p.name_on_pan),
          ("Address", p.address), ("Status", "Individual"),
          ("Form Number", form), ("e-Filing Acknowledgement Number", ack),
          ("Date of filing", dmon(filed)), ("Nature of business / profession", p.org.name)]
    yy = 758
    for k, v in kv:
        d.text(45, yy, k, 8.5)
        d.text(220, yy, f": {v}", 8.5)
        yy -= 15
    d.bold(45, 620, "Taxable Income and Tax details", 10)
    rows = [("1. Gross Total Income", gti), ("2. Total Deductions under Chapter VI-A", ded),
            ("3. Total Income", income), ("4. Book Profit under MAT, where applicable", 0),
            ("5. Net tax payable", tax), ("6. Interest and Fee Payable", 0),
            ("7. Total tax, interest and Fee payable", tax), ("8. Taxes Paid", paid),
            ("9. (+) Tax Payable / (-) Refundable (7-8)", 0)]
    yy = 600
    for k, v in rows:
        d.text(45, yy, k, 9)
        d.text(550, yy, inr(v, 0), 9, align="r")
        d.line(40, yy - 4, W - 40, yy - 4, 0.2)
        yy -= 18
    d.para(45, yy - 20, f"This return has been digitally signed by {p.name_on_pan} in the capacity of Self having "
                        f"PAN {p.pan} from IP address 10.x.x.x on {dmon(filed)}. DSC/EVC verified.", W - 90, 8.5)
    d.footer(SYNTH)
    data = d.finish("Income Tax e-Filing Portal (ReportLab PDF Library)", "e-Filing ITR-V",
                    datetime(filed.year, filed.month, filed.day, 16, 22, 40))
    return data, {"ay": ay, "total_income": float(income), "gross_total_income": float(gti), "form": form,
                  "tax_paid": float(paid), "name": p.name_on_pan}


# =========================================================================== bank statement
UPI_MERCHANTS = [("SWIGGY", "swiggy@ybl", 180, 900), ("ZOMATO", "zomato@hdfcbank", 200, 1100),
                 ("BLINKIT", "blinkit@icici", 250, 1800), ("BIGBASKET", "bigbasket@axis", 600, 3200),
                 ("AMAZON PAY", "amazonpay@apl", 300, 4500), ("UBER INDIA", "uber@axisbank", 150, 650),
                 ("RELIANCE SMART", "rsmart@kotak", 700, 3400), ("APOLLO PHARMACY", "apollo@icici", 150, 1600),
                 ("INDIAN OIL PETROL", "iocl@sbi", 500, 2800), ("JIO PREPAID", "jio@sbi", 299, 899),
                 ("PVR CINEMAS", "pvr@icici", 400, 1600), ("MYNTRA", "myntra@ybl", 600, 3800)]
GAMBLING = [("DREAM11", "dream11@ybl"), ("RUMMYCIRCLE", "rummycircle@icici"), ("JUNGLEE RUMMY", "jungleerummy@axis"),
            ("STAKE BET", "stakebet@paytm"), ("POKERBAAZI", "pokerbaazi@ybl"), ("MPL TEEN PATTI", "mpl@icici")]


class Stmt:
    def __init__(self, p: Persona, rng: random.Random) -> None:
        self.p = p
        self.rng = rng
        self.events: list[tuple[date, int, str, float]] = []  # (date, order, narration, signed amount)

    def add(self, d: date, narr: str, amt: float, order: int = 5) -> None:
        self.events.append((d, order, narr, round(amt, 2)))

    def ref(self) -> str:
        return f"{self.rng.randint(10**11, 10**12 - 1)}"


def stmt_months(p: Persona) -> list[tuple[int, int]]:
    out = []
    y, m = 2026, 10
    for _ in range(p.months):
        out.insert(0, (y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def build_transactions(p: Persona, net_salary: float, rng: random.Random) -> list[dict[str, Any]]:
    st = Stmt(p, rng)
    months = stmt_months(p)
    rnd = "round" in p.patterns
    bounce_months = {months[1], months[3], months[4]} if "bounces" in p.patterns else set()
    monthly_income = net_salary if p.employment == "SALARIED" else p.itr[-1][1] / 12

    def amt(lo: float, hi: float) -> float:
        v = rng.uniform(lo, hi)
        return float(round(v / 1000) * 1000 or 1000) if rnd else round(v, 2) if rng.random() < 0.5 else float(round(v))

    for (y, m) in months:
        dim = monthrange(y, m)[1]
        mon = MONTHS[m - 1][:3].upper()
        # ---------------- income
        if p.employment == "SALARIED":
            sd = last_working_day(y, m)
            st.add(sd, f"NEFT CR-{p.org.ifsc}-{p.org.short} SALARY {mon} {y}", net_salary, 1)
        else:
            receipts = monthly_income * (1.55 if "cash_business" in p.patterns else 1.35)
            if "cash_business" in p.patterns:
                upi_total = receipts * 0.80
                for wk in range(4):
                    st.add(date(y, m, min(7 * wk + rng.randint(1, 4), dim)),
                           f"UPI/CR/{st.ref()}/PHONEPE MERCHANT SETTLEMENT/SHREE GANESH KIRANA",
                           round(upi_total / 4 * rng.uniform(0.85, 1.15), 2))
                for _ in range(2):
                    st.add(date(y, m, rng.randint(2, dim)), "CASH DEP CDM MALHARGANJ INDORE",
                           float(rng.randint(10, 18) * 1000 + rng.choice([0, 500])))
                if (y, m) in (months[3], months[8]):
                    st.add(date(y, m, 18), "CASH DEP BRANCH MALHARGANJ-FESTIVE SALES", 125500.0 if m != 3 else 110000.0)
            elif "clinic" in p.patterns:
                for wk in range(4):
                    st.add(date(y, m, min(7 * wk + rng.randint(2, 6), dim)),
                           f"NEFT CR-PNLB0000001-PINELABS POS SETTLEMENT-{p.org.short}",
                           round(receipts * 0.16 * rng.uniform(0.8, 1.2), 2))
                for ins in ("STARCARE TPA HEALTH CLAIMS", "MEDISHIELD INSURANCE TPA"):
                    st.add(date(y, m, rng.randint(8, 25)), f"NEFT CR-MDTP0000045-{ins}-{p.org.short}",
                           round(receipts * 0.15 * rng.uniform(0.8, 1.2), 2))
                for _ in range(4):
                    st.add(date(y, m, rng.randint(1, dim)), f"UPI/CR/{st.ref()}/PATIENT CONSULT/{p.org.short}",
                           round(rng.uniform(800, 4500), 2))
            else:  # professional / trader
                clients = (["SUNRISE TEXTILES PVT LTD", "KAPOOR & SONS LLP", "ORBIT LOGISTICS LTD", "NAVKAR JEWELS"]
                           if p.pid == "p03" else
                           ["SINGH MOTOR GARAGE", "DELHI WHEELS SERVICE", "CITY AUTO WORKS", "SHARMA CARRIERS"])
                k = rng.randint(4, 6)
                for i in range(k):
                    st.add(date(y, m, rng.randint(1, dim)),
                           f"NEFT CR-{p.org.ifsc}-{clients[i % len(clients)]}-{'PROF FEES' if p.pid == 'p03' else 'INV PMT'}",
                           round(receipts / k * rng.uniform(0.7, 1.3), 2))
            # business outflows
            st.add(date(y, m, 7), f"NEFT DR-{p.bank.ifsc}-STAFF SALARY {mon}", -round(receipts * 0.12, 2), 6)
            st.add(date(y, m, 20), f"GST PMT-CPIN {y % 100}{m:02d}{p.pid[1:]}0{rng.randint(10**6, 10**7 - 1)}",
                   -round(receipts * 0.04, 2), 6)
            if m in (6, 9, 12, 3):
                st.add(date(y, m, 14), "CBDT TAX-ITNS280-ADVANCE TAX", -round(monthly_income * 0.55, 2), 6)
            n_sup = 3 if p.pid == "p04" else 2 if p.pid == "p10" else 1
            for _ in range(n_sup):
                sup = rng.choice(["AGARWAL WHOLESALE TRADERS", "MALWA FMCG DISTRIBUTORS", "PARLE AGENCY INDORE"]
                                 if p.pid == "p04" else ["AUTOCOMP DISTRIBUTORS", "NAROLA PARTS DEPOT"]
                                 if p.pid == "p10" else ["MEDLINE SURGICALS", "OFFICE RENT-LANDLORD"])
                share = 0.2 if p.pid == "p04" else 0.15 if p.pid == "p10" else 0.08
                st.add(date(y, m, rng.randint(3, 26)), f"RTGS DR-{p.bank.ifsc}-{sup}", -round(receipts * share * rng.uniform(0.85, 1.15), 2), 6)
        # ---------------- obligations
        for narr, emi_amt, day in p.emis:
            if (y, m) in bounce_months and "TW LOAN" in narr:
                st.add(date(y, m, day), f"ECS RTN CHGS-{narr.split('-', 1)[1].strip()}-INSUFF FUNDS", -590.0, 2)
                st.add(date(y, m, day + 7), f"{narr} RE-PRESENTED", -emi_amt, 3)
            else:
                st.add(date(y, m, day), narr, -emi_amt, 3)
        if p.pid in ("p01", "p05", "p07", "p12"):
            rent = {"p01": 24500, "p05": 32000, "p07": 22000, "p12": 14500}[p.pid]
            st.add(date(y, m, 2), f"IMPS/P2A/{st.ref()}/LANDLORD RENT {mon}", -float(rent), 4)
        if p.pid in ("p01", "p11", "p03"):
            sip = {"p01": 15000, "p11": 75000, "p03": 50000}[p.pid]
            st.add(date(y, m, 10), "ACH D- BSE STAR MF-SIP INSTALMENT", -float(sip), 4)
        st.add(date(y, m, rng.randint(8, 14)), "BILLDESK*ELECTRICITY BILL PAYMENT", -round(rng.uniform(900, 3400), 2))
        st.add(date(y, m, rng.randint(15, 20)), "AIRTEL POSTPAID BILLPAY", -float(rng.choice([599, 799, 999])))
        if p.pid == "p08":
            st.add(date(y, m, 6), "LIC PREMIUM ECS-POLICY XXXXX4410", -2310.0, 4)
        if p.pid == "p06":
            st.add(date(y, m, 1 if m % 2 else 2), f"IMPS/P2A/{st.ref()}/NARSIMHA GOUD/FAMILY", -7000.0, 4)
        # ---------------- discretionary spends
        budget = monthly_income * p.spend_level
        spent = 0.0
        n_upi = 0
        while spent < budget * 0.75 and n_upi < 18:
            mer, vpa, lo, hi = rng.choice(UPI_MERCHANTS)
            a = amt(lo, hi)
            st.add(date(y, m, rng.randint(1, dim)), f"UPI/DR/{st.ref()}/{mer}/{vpa}", -a)
            spent += a
            n_upi += 1
        if spent < budget * 0.7:
            st.add(date(y, m, 22), f"CC BILLPAY-{p.bank.name.split()[0].upper()} CARD XXXX{p.mobile[-4:]}",
                   -round(budget * 0.75 - spent, 2), 5)
        for _ in range(rng.randint(1, 2)):
            a = float(rng.choice([2000, 3000, 5000, 10000]))
            st.add(date(y, m, rng.randint(1, dim)), f"ATM WDL-ATM ID S1C{rng.randint(1000, 9999)} {p.city.upper()}", -a)
            spent += a
        if not rnd:
            a = round(rng.uniform(1500, 6000), 2)
            st.add(date(y, m, rng.randint(1, dim)), f"POS 4591XXXXXXXX{rng.randint(1000, 9999)} DMART {p.city.upper()}", -a)
        if "gambling" in p.patterns:
            for _ in range(rng.randint(9, 14)):
                mer, vpa = rng.choice(GAMBLING)
                st.add(date(y, m, rng.randint(1, dim)), f"UPI/DR/{st.ref()}/{mer}/{vpa}",
                       -float(rng.choice([500, 1000, 1500, 2000, 2500, 5000, 7500, 10000])))
            if m % 3 == 0:
                st.add(date(y, m, rng.randint(1, dim)), f"UPI/CR/{st.ref()}/DREAM11 WINNINGS/dream11@ybl",
                       float(rng.choice([1200, 3400, 8800])))
            st.add(date(y, m, rng.randint(5, 25)), f"NEFT DR-{p.bank.ifsc}-ARTHVEDA BROKING-TRADING A/C",
                   -float(rng.randint(1, 3) * 10000))
        if rng.random() < 0.35:
            st.add(date(y, m, rng.randint(1, dim)), f"UPI/CR/{st.ref()}/FRIEND REFUND/gpay", float(amt(300, 2500)))
        if m in (3, 6, 9, 12):
            st.add(date(y, m, monthrange(y, m)[1]), f"INT.PD:01-{m - 2:02d}-{y} TO {monthrange(y, m)[1]}-{m:02d}-{y}", 0.0, 9)

    # ---------------- running balance (discretionary debits are dropped if they would overdraw)
    st.events.sort(key=lambda e: (e[0], e[1], e[2]))
    bal = p.opening_balance
    rows: list[dict[str, Any]] = []
    floor = 800.0
    for d, order, narr, a in st.events:
        if narr.startswith("INT.PD"):
            a = round(max(bal, 0) * 0.03 / 4, 2) or 1.0
        if a < 0 and order == 5 and bal + a < floor:
            continue
        bal = round(bal + a, 2)
        rows.append({"date": d, "description": narr, "amount": a, "balance": bal})
    return rows


def render_bank_statement(p: Persona, rows: list[dict[str, Any]], rng: random.Random) -> bytes:
    b = p.bank
    months = stmt_months(p)
    start = date(months[0][0], months[0][1], 1)
    end = date(months[-1][0], months[-1][1], monthrange(*months[-1])[1])
    d = Doc("Account Statement")
    fmt = b.date_fmt
    code = b.ifsc[:4]
    x_date, x_narr, x_ref, x_val, x_wd, x_dep, x_bal = 32, 80, 290, 352, 458, 514, 568
    per_page_first, per_page = 46, 62
    page_no = 1
    total_pages = 1 + max(0, (len(rows) - per_page_first + per_page - 1) // per_page)

    def header_band(first: bool) -> float:
        if first:
            d.rect(30, 772, W - 60, 48, fill=(0.12, 0.25, 0.45))
            d.text(45, 800, b.name.upper(), 15, "Helvetica-Bold", color=(1, 1, 1))
            d.text(45, 784, f"Branch: {b.branch}   |   IFSC: {b.ifsc}   |   MICR: {rng.randint(100000000, 999999999)}", 8, color=(1, 1, 1))
            d.bold(W / 2, 752, "STATEMENT OF ACCOUNT", 11, "c")
            info = [("Account Holder", p.name_on_pan, "Account No", b.account_no),
                    ("Address", p.address[:62], "Account Type", "Savings Account" if p.employment == "SALARIED" else "Current Account"),
                    ("", p.address[62:], "Customer ID", f"{code}{rng.randint(1000000, 9999999)}"),
                    ("Mobile", "XXXXXX" + p.mobile[-4:], "Currency", "INR"),
                    ("Statement Period", f"{dmy(start)} to {dmy(end)}", "Nomination", "Registered")]
            yy = 732
            for a1, b1, a2, b2 in info:
                d.text(40, yy, a1, 8)
                d.text(118, yy, (": " if a1 else "  ") + b1, 8)
                d.text(370, yy, a2, 8)
                d.text(445, yy, ": " + b2, 8)
                yy -= 12
            top = yy - 8
        else:
            d.bold(40, 812, f"{b.name.upper()}  -  Statement of Account  -  A/c {b.account_no}", 8)
            top = 800
        d.rect(30, top - 14, W - 60, 14, fill=(0.88, 0.9, 0.95))
        for x, t, al in ((x_date, "Date", "l"), (x_narr, "Narration", "l"), (x_ref, "Chq./Ref.No.", "l"),
                         (x_val, "Value Dt", "l"), (x_wd, "Withdrawal Amt.", "r"), (x_dep, "Deposit Amt.", "r"),
                         (x_bal, "Closing Balance", "r")):
            d.bold(x, top - 10, t, 7, al)
        return top - 26

    y = header_band(True)
    d.text(x_narr, y, "OPENING BALANCE", 7)
    d.text(x_bal, y, inr(p.opening_balance), 7, align="r")
    y -= 11
    count_on_page = 0
    limit = per_page_first
    for r in rows:
        if count_on_page >= limit:
            d.footer(f"Page {page_no} of {total_pages}   |   {SYNTH}")
            d.page()
            page_no += 1
            y = header_band(False)
            count_on_page = 0
            limit = per_page
        dt = r["date"]
        d.text(x_date, y, dt.strftime(fmt), 7)
        narr = r["description"]
        d.text(x_narr, y, narr[:46], 6.6)
        d.text(x_ref, y, f"{code}N{dt.strftime('%y%j')}{rng.randint(10000, 99999)}" if "NEFT" in narr or "RTGS" in narr else "0000000", 6.6)
        d.text(x_val, y, dt.strftime(fmt), 7)
        if r["amount"] < 0:
            d.text(x_wd, y, inr(-r["amount"]), 7, align="r")
        else:
            d.text(x_dep, y, inr(r["amount"]), 7, align="r")
        d.text(x_bal, y, inr(r["balance"]), 7, align="r")
        y -= 11
        count_on_page += 1
    debits = sum(-r["amount"] for r in rows if r["amount"] < 0)
    credits = sum(r["amount"] for r in rows if r["amount"] > 0)
    y -= 8
    d.line(30, y + 6, W - 30, y + 6)
    d.bold(40, y - 6, "STATEMENT SUMMARY", 8)
    d.text(40, y - 20, f"Opening Balance: {inr(p.opening_balance)}   Dr Count: {sum(1 for r in rows if r['amount'] < 0)}   "
                       f"Cr Count: {sum(1 for r in rows if r['amount'] > 0)}", 7.5)
    d.text(40, y - 32, f"Debits: {inr(debits)}   Credits: {inr(credits)}   Closing Balance: {inr(rows[-1]['balance'])}", 7.5)
    d.text(40, y - 50, "*** Computer generated statement - does not require signature ***", 7)
    d.footer(f"Page {page_no} of {total_pages}   |   {SYNTH}")
    return d.finish(f"{b.name} e-Statement Engine (ReportLab PDF Library)", f"{b.name} CBS",
                    datetime(2026, 11, 3, 9, 14, 55))


# =========================================================================== property docs
def render_deed(p: Persona) -> tuple[bytes, str, dict[str, Any]]:
    pr = p.prop
    assert pr is not None
    title = {"AGREEMENT_FOR_SALE": "AGREEMENT FOR SALE", "SALE_DEED": "SALE DEED",
             "TITLE_DEED": "TITLE DEED - CONVEYANCE (SALE DEED)"}[pr.deed_type]
    fname = {"AGREEMENT_FOR_SALE": "agreement_for_sale", "SALE_DEED": "sale_deed", "TITLE_DEED": "title_deed"}[pr.deed_type]
    owners = p.name_on_pan.title()
    if p.co_applicant and pr.deed_type != "TITLE_DEED":
        owners += f" and {p.co_applicant['name']}"
    stamp = round(pr.consideration * (0.06 if "Mumbai" in pr.address or "Pune" in pr.address else 0.05), -2)
    d = Doc(title)
    d.rect(150, 760, W - 300, 60, fill=(0.96, 0.94, 0.86))
    d.bold(W / 2, 800, "NON JUDICIAL", 10, "c")
    d.text(W / 2, 786, f"e-Stamp Certificate No. IN-{pr.registration_no.split('/')[0]}-{pr.reg_date.strftime('%d%m%Y')}", 8, align="c")
    d.text(W / 2, 772, f"Stamp Duty Paid: Rs. {inr(stamp, 0)}", 8, align="c")
    d.bold(W / 2, 735, title, 15, "c")
    y = 712
    intro = (f"THIS {title.split(' - ')[0]} is made and executed at {pr.sro.split(',')[-1].strip()} on "
             f"{pr.reg_date.strftime('%d %B %Y')} BETWEEN {pr.seller}, hereinafter called the VENDOR, of the ONE PART "
             f"AND {owners}, residing at {p.address}, hereinafter called the PURCHASER(S), of the OTHER PART.")
    y = d.para(45, y, intro, W - 90, 9)
    y -= 6
    y = d.para(45, y, "WHEREAS the Vendor is the absolute owner of the property described in the Schedule below, having "
                      "clear and marketable title, and has agreed to sell the same to the Purchaser(s) for the consideration "
                      "mentioned herein, free from all encumbrances, charges, liens and attachments.", W - 90, 9)
    y -= 10
    d.bold(45, y, "SCHEDULE OF PROPERTY", 10)
    y -= 16
    rows = [("Property Address", pr.address), ("Description", pr.description),
            ("Carpet Area", f"{pr.area_sqft:.0f} sq. ft."),
            ("Total Consideration", f"Rs. {inr(pr.consideration)} (Rupees {words(pr.consideration)} Only)"),
            ("Owner / Purchaser", owners), ("Vendor", pr.seller),
            ("Encumbrance", "Nil - property is free from all encumbrances" if pr.encumbrance == "NIL" else pr.encumbrance),
            ("Registration No.", pr.registration_no), ("Date of Registration", dmy(pr.reg_date)),
            ("Registering Office", pr.sro)]
    for k, v in rows:
        d.text(45, y, k, 9)
        y = d.para(170, y, f": {v}", W - 215, 9)
        y -= 2
    y -= 8
    y = d.para(45, y, f"NOW THIS DEED WITNESSETH that in consideration of the sum of Rs. {inr(pr.consideration)} paid by the "
                      "Purchaser(s) to the Vendor (the receipt whereof the Vendor hereby admits and acknowledges), the Vendor "
                      "doth hereby convey, transfer and assure unto the Purchaser(s) the said property TO HAVE AND TO HOLD the "
                      "same absolutely and forever.", W - 90, 9)
    y -= 26
    d.text(60, y, "VENDOR", 9)
    d.text(260, y, "PURCHASER(S)", 9)
    d.text(440, y, "WITNESSES", 9)
    d.text(60, y - 40, "(Sd/-)", 8)
    d.text(260, y - 40, "(Sd/-)", 8)
    d.text(440, y - 40, "1. (Sd/-)  2. (Sd/-)", 8)
    d.footer(SYNTH)
    data = d.finish("Inspector General of Registration - e-Registration (ReportLab PDF Library)", "e-Registration",
                    datetime(pr.reg_date.year, pr.reg_date.month, pr.reg_date.day, 15, 40, 0))
    facts = {"property_address": pr.address, "consideration_value": float(pr.consideration),
             "registration_no": pr.registration_no, "area_sqft": float(pr.area_sqft), "deed_type": pr.deed_type,
             "encumbrance": pr.encumbrance}
    return data, fname, facts


def render_valuation(p: Persona) -> tuple[bytes, dict[str, Any]]:
    pr = p.prop
    assert pr is not None
    mv = pr.market_value
    distress = round(mv * 0.80, -3)
    realisable = round(mv * 0.90, -3)
    rate = round(mv / pr.area_sqft)
    guideline = round(mv * 0.72, -3)
    insp = APP_DATE - timedelta(days=4)
    d = Doc("Valuation Report")
    d.rect(30, 765, W - 60, 52, fill=(0.94, 0.96, 0.94))
    d.bold(45, 798, pr.valuer.split(" (")[0].upper(), 13)
    d.text(45, 784, "(" + pr.valuer.split(" (")[1] if "(" in pr.valuer else "", 8)
    d.text(45, 772, "Chartered Engineers | Registered Valuers (IBBI) | Panel valuer for banks & HFCs", 7.5)
    d.bold(W / 2, 740, "VALUATION REPORT (TECHNICAL)", 13, "c")
    d.text(W / 2, 726, f"Ref: VR/{p.pid.upper()}/{insp.strftime('%Y%m')}/{100 + int(p.pid[1:]) * 7}    Date: {dmy(APP_DATE - timedelta(days=2))}", 8.5, align="c")
    rows = [("Name of the Applicant / Owner", p.name_on_pan.title()), ("Purpose of Valuation", "Mortgage - " + ("Home Loan" if p.product == "HOME_LOAN" else "Loan Against Property")),
            ("Date of Inspection", dmy(insp)), ("Property Address", pr.address),
            ("Type of Property", "Residential" if p.property_type == "RESIDENTIAL" else "Commercial"),
            ("Description", pr.description), ("Carpet Area", f"{pr.area_sqft:.0f} sq. ft."),
            ("Adopted Rate", f"Rs. {inr(rate, 0)} per sq. ft."),
            ("Govt. Guideline / Ready Reckoner Value", f"Rs. {inr(guideline)}"),
            ("Fair Market Value", f"Rs. {inr(mv)}"),
            ("Realisable Value (90%)", f"Rs. {inr(realisable)}"),
            ("Distress Value (80%)", f"Rs. {inr(distress)}"),
            ("Agreement / Purchase Value", f"Rs. {inr(pr.consideration)}"),
            ("Age of Building / Residual Life", "6 years / 54 years" if pr.deed_type != "TITLE_DEED" else "14 years / 46 years"),
            ("Occupancy", "Self-occupied" if pr.deed_type == "TITLE_DEED" else "Vacant - ready possession")]
    y = 700
    for k, v in rows:
        d.text(45, y, k, 9)
        y = d.para(250, y, f": {v}", W - 295, 9)
        d.line(40, y + 8, W - 40, y + 8, 0.2)
        y -= 4
    y -= 8
    y = d.para(45, y, f"Remarks: The property is approached by a motorable road, construction is as per sanctioned plan and "
                      f"in good condition. In our opinion the fair market value of the above property is Rs. {inr(mv)} "
                      f"(Rupees {words(mv)} Only).", W - 90, 9)
    d.text(380, y - 40, "For " + pr.valuer.split(" (")[0], 9)
    d.text(380, y - 70, "(Sd/-) Authorised Valuer", 8.5)
    d.footer(SYNTH)
    data = d.finish("ValuerDesk Report Writer (ReportLab PDF Library)", "ValuerDesk",
                    datetime(2026, 11, 8, 17, 12, 3))
    return data, {"market_value": float(mv), "distress_value": float(distress), "realisable_value": float(realisable),
                  "area_sqft": float(pr.area_sqft), "property_address": pr.address}


# =========================================================================== card images
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("VeraBd.ttf" if bold else "Vera.ttf")), size)


def _speckle(img: Image.Image, rng: random.Random, n: int) -> None:
    px = img.load()
    w, h = img.size
    for _ in range(n):
        x, y = rng.randrange(w), rng.randrange(h)
        v = rng.randint(90, 180)
        px[x, y] = (v, v, v) if img.mode == "RGB" else v  # type: ignore[index]


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_pan_card(p: Persona, rng: random.Random) -> bytes:
    w, h = 1012, 638
    img = Image.new("RGB", (w, h), (214, 232, 242))
    dr = ImageDraw.Draw(img)
    for i in range(0, h, 6):
        dr.line([(0, i), (w, i)], fill=(208, 228, 240))
    dr.rectangle([0, 0, w, 120], fill=(26, 82, 140))
    dr.text((40, 22), "INCOME TAX DEPARTMENT", font=_font(38, True), fill=(255, 255, 255))
    dr.text((600, 30), "GOVT. OF INDIA", font=_font(32, True), fill=(255, 255, 255))
    dr.text((40, 140), "Permanent Account Number Card", font=_font(26), fill=(20, 20, 20))
    dr.text((40, 180), p.pan, font=_font(52, True), fill=(10, 10, 10))
    dr.rectangle([760, 150, 960, 380], outline=(90, 90, 90), width=3, fill=(235, 235, 235))
    dr.text((800, 250), "PHOTO", font=_font(30), fill=(150, 150, 150))
    rows = [("Name", p.name_on_pan), ("Father's Name", p.father), ("Date of Birth", p.dob.strftime("%d/%m/%Y"))]
    y = 270
    for k, v in rows:
        dr.text((40, y), k, font=_font(22), fill=(60, 60, 60))
        dr.text((40, y + 28), v, font=_font(32, True), fill=(10, 10, 10))
        y += 92
    dr.text((700, 560), "Signature", font=_font(20), fill=(80, 80, 80))
    dr.text((40, 600), "SPECIMEN - synthetic test data", font=_font(16), fill=(120, 120, 120))
    img = img.rotate(rng.uniform(-1.2, 1.2), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(245, 245, 245))
    _speckle(img, rng, 2500)
    return _to_png(img.filter(ImageFilter.GaussianBlur(0.6)).quantize(64).convert("RGB"))


def render_aadhaar_card(p: Persona, rng: random.Random) -> bytes:
    w, h = 1012, 1300
    img = Image.new("RGB", (w, h), (250, 250, 247))
    dr = ImageDraw.Draw(img)
    for top in (0, 662):
        dr.rectangle([0, top, w, top + 100], fill=(255, 153, 51))
        dr.rectangle([0, top + 100, w, top + 112], fill=(19, 136, 8))
    dr.text((300, 28), "GOVERNMENT OF INDIA", font=_font(40, True), fill=(20, 20, 20))
    dr.rectangle([40, 150, 270, 420], outline=(90, 90, 90), width=3, fill=(232, 232, 232))
    dr.text((95, 270), "PHOTO", font=_font(30), fill=(150, 150, 150))
    dr.text((310, 160), p.name_on_pan.title(), font=_font(36, True), fill=(10, 10, 10))
    dr.text((310, 220), f"DOB: {p.dob.strftime('%d/%m/%Y')}", font=_font(30), fill=(10, 10, 10))
    dr.text((310, 270), {"M": "MALE", "F": "FEMALE"}.get(p.gender, "OTHER"), font=_font(30), fill=(10, 10, 10))
    masked = f"XXXX XXXX {p.aadhaar[-4:]}"
    dr.text((250, 480), masked, font=_font(60, True), fill=(10, 10, 10))
    dr.line([(40, 580), (970, 580)], fill=(200, 30, 30), width=4)
    dr.text((260, 595), "Aadhaar - Aam Aadmi ka Adhikar", font=_font(26, True), fill=(200, 30, 30))
    dr.text((300, 690), "UNIQUE IDENTIFICATION AUTHORITY OF INDIA", font=_font(26, True), fill=(20, 20, 20))
    dr.text((40, 800), "Address:", font=_font(28, True), fill=(10, 10, 10))
    rel = "S/O" if p.gender == "M" else "W/O" if p.pid in ("p02",) else "D/O"
    addr_lines = [f"{rel}: {p.father.title()},"]
    words_ = p.address.split(" ")
    line = ""
    for wd in words_:
        if len(line) + len(wd) > 44:
            addr_lines.append(line.strip())
            line = ""
        line += wd + " "
    addr_lines.append(line.strip())
    y = 845
    for ln in addr_lines:
        dr.text((40, y), ln, font=_font(30), fill=(10, 10, 10))
        y += 44
    dr.text((250, 1130), masked, font=_font(52, True), fill=(10, 10, 10))
    dr.text((40, 1250), "Masked Aadhaar (only last 4 digits visible) - SPECIMEN, synthetic test data",
            font=_font(18), fill=(110, 110, 110))
    img = img.rotate(rng.uniform(-1.0, 1.0), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(245, 245, 245))
    _speckle(img, rng, 3000)
    return _to_png(img.filter(ImageFilter.GaussianBlur(0.5)).quantize(64).convert("RGB"))


def pdf_to_scan(pdf: bytes, rng: random.Random, dpi: int = 130) -> bytes:
    """Rasterise page 1 like a flatbed scan: grey, slight skew, speckle, mild blur."""
    if not shutil.which("pdftoppm"):
        raise SystemExit("pdftoppm (poppler-utils) is required to render scanned documents")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.pdf"
        src.write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-singlefile", "-f", "1", "-l", "1",
                        str(src), str(Path(td) / "out")], check=True)
        img = Image.open(Path(td) / "out.png").convert("L")
    img = img.point(lambda v: int(28 + v * 0.86))  # lower contrast, greyish paper
    img = img.rotate(rng.uniform(-1.4, 1.4), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=246)
    _speckle(img, rng, 9000)
    img = img.filter(ImageFilter.GaussianBlur(0.45))
    img = img.quantize(16).convert("L")
    return _to_png(img)


# =========================================================================== persona assembly
def build_persona(p: Persona, out: Path, make_zip: bool) -> dict[str, Any]:
    rng = random.Random(f"finpilot-{p.pid}")
    pdir = out / p.pid
    if pdir.exists():
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)
    docs: dict[str, dict[str, Any]] = {}

    def save(stem: str, scan_key: str, pdf: bytes, doc_type: str, facts: dict[str, Any]) -> None:
        if scan_key in p.scans:
            fname, data, source = f"{stem}.png", pdf_to_scan(pdf, rng), "ocr"
        else:
            fname, data, source = f"{stem}.pdf", pdf, "text"
        (pdir / fname).write_bytes(data)
        docs[fname] = {"doc_type": doc_type, "source": source, "fields": facts}

    # identity
    (pdir / "pan_card.png").write_bytes(render_pan_card(p, rng))
    docs["pan_card.png"] = {"doc_type": "PAN", "source": "ocr", "fields": {
        "name": p.name_on_pan, "dob": p.dob.isoformat(), "pan_masked": f"XXXXX{p.pan[5:]}", "father_name": p.father}}
    (pdir / "aadhaar_card.png").write_bytes(render_aadhaar_card(p, rng))
    docs["aadhaar_card.png"] = {"doc_type": "AADHAAR", "source": "ocr", "fields": {
        "name": p.name_on_pan.title(), "dob": p.dob.isoformat(), "aadhaar_masked": f"XXXX XXXX {p.aadhaar[-4:]}",
        "gender": p.gender, "pincode": p.address[-6:]}}

    net_salary = 0.0
    slips: list[dict[str, Any]] = []
    form16: dict[str, Any] = {}
    itrs: list[dict[str, Any]] = []
    if p.employment == "SALARIED":
        s = salary_structure(p)
        net_salary = s["net"]
        shown = forged_structure(p, s) if p.forged else s
        for (y, m) in SLIP_MONTHS:
            stem = f"salary_slip_{y}-{m:02d}"
            facts = {"month": f"{y}-{m:02d}", "employer": p.org.name, "employee_name": p.name_on_pan.title(),
                     "gross": shown["gross"], "net_pay": shown["net"], "total_deductions": shown["total_deductions"]}
            save(stem, stem, render_salary_slip(p, y, m, shown), "SALARY_SLIP", facts)
            slips.append(facts)
        f16, f16facts = render_form16(p, s["gross"])
        save("form16_ay2026-27", "form16", f16, "FORM16", f16facts)
        form16 = f16facts
    else:
        for ay, inc in p.itr:
            data, facts = render_itr_v(p, ay, inc)
            save(f"itr_v_ay{ay}", f"itr_{ay}", data, "ITR", facts)
            itrs.append(facts)

    rows = build_transactions(p, net_salary, rng)
    (pdir / "bank_statement.pdf").write_bytes(render_bank_statement(p, rows, rng))
    cats = categorize_expected(rows)
    months = stmt_months(p)
    docs["bank_statement.pdf"] = {"doc_type": "BANK_STATEMENT", "source": "text", "fields": {
        "account_holder": p.name_on_pan, "bank_name": p.bank.name, "n_transactions": len(rows),
        "opening_balance": p.opening_balance, "closing_balance": rows[-1]["balance"],
        "period_start": date(months[0][0], months[0][1], 1).isoformat(),
        "period_end": date(2026, 10, 31).isoformat(),
        "total_credits": round(sum(r["amount"] for r in rows if r["amount"] > 0), 2),
        "total_debits": round(sum(-r["amount"] for r in rows if r["amount"] < 0), 2),
        **cats}}

    deed, deed_stem, deed_facts = render_deed(p)
    save(deed_stem, "sale_deed", deed, "SALE_DEED", deed_facts)
    val, val_facts = render_valuation(p)
    save("valuation_report", "valuation_report", val, "VALUATION_REPORT", val_facts)

    form: dict[str, Any] = {
        "product": p.product, "applicant_name": p.form_name, "dob": p.dob.isoformat(), "gender": p.gender,
        "mobile_masked": "XXXXXX" + p.mobile[-4:], "city": p.city, "employment_type": p.employment,
        "employer_or_business": p.org.name, "years_in_job": p.years_in_job,
        "declared_monthly_income": float(p.declared_income if p.declared_income is not None else round(net_salary, -3)),
        "existing_emi": p.existing_emi, "bureau_score": p.bureau, "loan_amount": p.loan_amount,
        "tenure_months": p.tenure, "property_value": p.property_value, "property_type": p.property_type,
        "property_city": p.city, "purpose": p.purpose, "lap_end_use": p.lap_end_use,
        "co_applicant": p.co_applicant, "is_first_home": p.is_first_home, "rate_type": "FLOATING",
    }
    persona_meta = {"id": p.pid, "title": p.title, "segment": p.segment, "story": p.story,
                    "expected_outcome": p.expected_outcome}
    (pdir / "application.json").write_text(json.dumps({**form, "persona": persona_meta}, indent=2) + "\n")

    expected_flags = {"p07": ["DOC_PRODUCER_SUSPICIOUS", "DOC_MODIFIED_AFTER_CREATION", "DOC_FONT_ANOMALY",
                              "DOC_ROUND_NUMBERS", "SALARY_CREDIT_MISMATCH"]}.get(p.pid, [])
    expected = {
        "persona_id": p.pid, "expected_outcome": p.expected_outcome, "acceptable_outcomes": p.acceptable_outcomes,
        "documents": docs,
        "facts": {
            "name": p.name_on_pan, "form_name": p.form_name, "dob": p.dob.isoformat(),
            "pan_masked": f"XXXXX{p.pan[5:]}", "aadhaar_masked": f"XXXX XXXX {p.aadhaar[-4:]}",
            "employment_type": p.employment, "employer": p.org.name,
            "actual_net_salary": round(net_salary, 2), "slip_net_pay": slips[0]["net_pay"] if slips else None,
            "declared_monthly_income": form["declared_monthly_income"],
            "form16": form16 or None, "itr": itrs or None,
            "property_market_value": val_facts["market_value"], "property_distress_value": val_facts["distress_value"],
            "consideration_value": deed_facts["consideration_value"], "registration_no": deed_facts["registration_no"],
            "statement_months": p.months, **{k: v for k, v in cats.items()},
        },
        "expected_flags": expected_flags,
        "forbidden_flag_severities": ["HIGH", "CRITICAL"] if p.pid in ("p01", "p02", "p03", "p09", "p12") else [],
        "missing_documents": [],
    }
    (pdir / "expected.json").write_text(json.dumps(expected, indent=2, default=str) + "\n")
    if make_zip:
        with zipfile.ZipFile(out / f"{p.pid}_upload_pack.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(pdir.iterdir()):
                if f.suffix in (".pdf", ".png"):
                    z.write(f, f"{p.pid}_upload_pack/{f.name}")
            z.writestr(f"{p.pid}_upload_pack/application_form.json", json.dumps(form, indent=2))
    return expected


def categorize_expected(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def has(r: dict[str, Any], *kw: str) -> bool:
        return any(k in r["description"].upper() for k in kw)
    return {
        "salary_credits": sum(1 for r in rows if r["amount"] > 0 and has(r, "SALARY") and not has(r, "STAFF")),
        "bounces": sum(1 for r in rows if has(r, "ECS RTN", "RETURN", "BOUNCE")),
        "gambling_txns": sum(1 for r in rows if r["amount"] < 0 and has(r, "DREAM11", "RUMMY", "BET", "POKER", "TEEN PATTI")),
        "cash_deposits": sum(1 for r in rows if r["amount"] > 0 and has(r, "CASH DEP")),
        "emi_debits": sum(1 for r in rows if r["amount"] < 0 and has(r, "LOAN EMI") and not has(r, "RTN")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="comma-separated persona ids")
    ap.add_argument("--zip", action="store_true", help="also write <pid>_upload_pack.zip per persona")
    ap.add_argument("--warm-ocr", action="store_true",
                    help="OCR every PNG once to fill the disk OCR cache (backend/.data/ocr_cache) for instant demos")
    a = ap.parse_args(argv)
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    a.out.mkdir(parents=True, exist_ok=True)
    for p in PERSONAS:
        if only and p.pid not in only:
            continue
        exp = build_persona(p, a.out, a.zip)
        size = sum(f.stat().st_size for f in (a.out / p.pid).iterdir())
        print(f"{p.pid}  {p.title[:58]:<58} {len(exp['documents']):>2} docs  {size / 1024:7.0f} KB  -> {p.expected_outcome}")
    if a.warm_ocr:
        sys.path.insert(0, str(REPO / "backend"))
        from app.documents import ocr

        pngs = [f.read_bytes() for p in PERSONAS if not only or p.pid in only for f in sorted((a.out / p.pid).glob("*.png"))]
        ocr.warm(pngs)
        print(f"OCR cache warmed for {len(pngs)} images with {ocr.engine_name()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
