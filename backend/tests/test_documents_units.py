"""Unit tests for document-layer helpers (no generated data / OCR needed)."""
from __future__ import annotations

import io
from datetime import date

import pytest
from reportlab.pdfgen import canvas

from app.documents import ocr, tamper
from app.documents._mask import redact_text
from app.documents.classify import classify
from app.documents.crosscheck import name_similarity, org_similarity, resegment
from app.documents.parsers import categorize, find_pan, parse_amount, parse_bank_statement
from app.documents.pipeline import process_documents
from app.schemas import DocType


@pytest.mark.parametrize("raw,val", [("1,45,000.00", 145000.0), ("Rs. 62,00,000/-", 6200000.0),
                                     ("1.45.000,00", 145000.0), ("86,40;000.00", 8640000.0),
                                     ("1,45,O00.00", 145000.0), ("200.00", 200.0), ("12,28,000", 1228000.0)])
def test_parse_amount_indian_and_ocr_noise(raw: str, val: float) -> None:
    assert parse_amount(raw) == val


def test_find_pan_repairs_ocr_confusions() -> None:
    assert find_pan("PAN: ABCPZ1234F") == "ABCPZ1234F"
    assert find_pan("PAN: A8CPZ12З4F".replace("З", "3")) == "ABCPZ1234F"
    assert find_pan("ABCPZI234F") == "ABCPZ1234F"
    assert find_pan("STATEMENT 2026") is None


def test_redaction_masks_pii_including_ocr_noisy_pan() -> None:
    text = "PAN ABCPZ1234F, noisy ABCPZ1Z34F, Aadhaar 4829 1736 5524, mob 9822014521, UPI/DR/612345678901/X"
    out = redact_text(text)
    assert "ABCPZ" not in out and "4829 1736" not in out and "9822014521" not in out and "612345678901" not in out
    assert "XXXXX1234F" in out and "XXXX XXXX 5524" in out


def test_name_similarity_handles_middle_names_titles_and_glued_ocr() -> None:
    assert name_similarity("Aarav Deshmukh", "AARAV SUNIL DESHMUKH") >= 0.95
    assert name_similarity("Dr Lakshmi Subramanian", "LAKSHMI SUBRAMANIAN") >= 0.95
    assert name_similarity("AARAVSUNILDESHMUKH", "Aarav Deshmukh") >= 0.9
    assert name_similarity("Rahul Sharma", "Vikram Singh") < 0.6
    assert resegment("AARAVSUNILDESHMUKH", {"AARAV", "SUNIL", "DESHMUKH"}) == "AARAV SUNIL DESHMUKH"


def test_org_similarity_narrations_and_acronyms() -> None:
    assert org_similarity("ACME INFOTECH", "Acme Infotech Pvt Ltd") >= 0.9
    assert org_similarity("VSPM NAGPUR", "Vidarbha Shikshan Prasarak Mandal (Govt. Aided)") >= 0.9
    assert org_similarity("ZENITH RETAIL", "Bluepeak Software Solutions Pvt Ltd") < 0.75


@pytest.mark.parametrize("desc,amt,cat", [
    ("NEFT CR-KTBK0000123-ACME INFOTECH SALARY OCT 2026", 145000, "SALARY"),
    ("ACH D- PRAGATI AUTO FINANCE LTD-CAR LOAN EMI", -18450, "EMI"),
    ("ECS RTN CHGS-SWIFTRIDE FINANCE-TW LOAN EMI-INSUFF FUNDS", -590, "BOUNCE"),
    ("UPI/DR/XXXXXXXX1234/DREAM11/dream11@ybl", -500, "GAMBLING"),
    ("CASH DEP CDM MALHARGANJ INDORE", 15000, "CASH_DEPOSIT"),
    ("ATM WDL-ATM ID S1C1234 PUNE", -2000, "CASH_WITHDRAWAL"),
    ("ACH D- BSE STAR MF-SIP INSTALMENT", -15000, "INVESTMENT"),
    ("NEFT DR-SHCB0000417-STAFF SALARY OCT", -50000, "TRANSFER_OUT"),
])
def test_transaction_categories(desc: str, amt: float, cat: str) -> None:
    assert categorize(desc, amt) == cat


def test_bank_statement_sign_from_running_balance() -> None:
    text = """STATEMENT OF ACCOUNT
Account Holder : TEST USER
Date       Narration                         Chq./Ref.No.   Value Dt   Withdrawal   Deposit   Closing Balance
           OPENING BALANCE                                                                     10,000.00
01/05/26   UPI/DR/123/SWIGGY                 0000000        01/05/26     500.00                 9,500.00
02/05/26   NEFT CR-ABCD0000001-ACME SALARY   ABCDN26122     02/05/26                50,000.00  59,500.00
"""
    meta, txns = parse_bank_statement(text)
    assert meta["opening_balance"] == 10000
    assert [t.amount for t in txns] == [-500.0, 50000.0]
    assert txns[1].category == "SALARY" and txns[0].date == date(2026, 5, 1)


def test_classifier_keywords_survive_glued_ocr_text() -> None:
    assert classify("FORMNO:16 PART.B Certificate under section203 TAN of the Deductor")[0] == DocType.FORM16
    assert classify("VALUATIONREPORT(TECHNICAL) FairMarketValue DistressValue")[0] == DocType.VALUATION_REPORT
    assert classify("hello world", "random.bin")[0] == DocType.UNKNOWN


def _pdf(producer: str, mixed_fonts: bool) -> bytes:
    from pypdf import PdfReader, PdfWriter

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 800, "ACME LTD PAYSLIP FOR THE MONTH OF AUGUST 2026")
    c.setFont("Helvetica", 10)
    c.drawString(50, 760, "Basic Salary")
    c.drawRightString(300, 760, "56,321.00")
    c.drawString(50, 740, "Gross Earnings")
    c.drawRightString(300, 740, "90,113.00")
    c.drawString(50, 720, "Total Deductions")
    c.drawRightString(300, 720, "10,100.00")
    c.drawString(50, 700, "NET PAY")
    c.setFont("Times-Roman" if mixed_fonts else "Helvetica", 10)
    c.drawRightString(300, 700, "80,013.00")
    c.save()
    w = PdfWriter(clone_from=PdfReader(io.BytesIO(buf.getvalue())))
    w.add_metadata({"/Producer": producer, "/CreationDate": "D:20260831100000+05'30'",
                    "/ModDate": "D:20261101100000+05'30'" if mixed_fonts else "D:20260831100000+05'30'"})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_tamper_heuristics_on_synthetic_pdf() -> None:
    bad = process_documents([("slip.pdf", _pdf("iLovePDF", True))], None)
    codes = {f.code for f in bad.flags}
    assert {"DOC_PRODUCER_SUSPICIOUS", "DOC_MODIFIED_AFTER_CREATION", "DOC_FONT_ANOMALY", "DOC_TAMPERED"} <= codes
    good = process_documents([("slip.pdf", _pdf("Acme HRMS", False))], None)
    assert not {f.code for f in good.flags} & tamper.TAMPER_CODES
    assert good.documents[0].doc_type == DocType.SALARY_SLIP
    assert good.documents[0].field("net_pay") == 80013.0


def test_duplicates_unreadable_and_missing_documents() -> None:
    pdf = _pdf("Acme HRMS", False)
    b = process_documents([("a.pdf", pdf), ("b.pdf", pdf), ("blank.txt", b"")], None)
    codes = [f.code for f in b.flags]
    assert "DOC_DUPLICATE" in codes and "DOC_UNREADABLE" in codes
    assert DocType.PAN in b.missing_documents and DocType.SALARY_SLIP not in b.missing_documents
    assert "INSUFFICIENT_SALARY_SLIPS" in codes


def test_ocr_disabled_degrades_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ENGINE", "none")
    ocr.reset_engine()
    try:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("L", (50, 50), 255).save(buf, format="PNG")
        b = process_documents([("pan_card.png", buf.getvalue())], None)
        assert b.documents[0].ocr_engine == "none"
        assert any(f.code == "DOC_UNREADABLE" for f in b.flags)
    finally:
        monkeypatch.delenv("OCR_ENGINE")
        ocr.reset_engine()


def test_ocr_disk_cache_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from documents_support import PERSONA_DIR

    card = PERSONA_DIR / "p01" / "pan_card.png"
    if not card.exists() or ocr.engine_name() == "none":
        pytest.skip("needs generated personas and an OCR engine")
    monkeypatch.setenv("OCR_CACHE_DIR", str(tmp_path))
    ocr.reset_engine()
    first = ocr.ocr_image(card.read_bytes())
    assert list(tmp_path.glob("*.json"))
    ocr.reset_engine()  # drop the in-memory cache
    second = ocr.ocr_image(card.read_bytes())
    assert second.text == first.text and "ocr-cache:disk" in second.notes
    ocr.reset_engine()
