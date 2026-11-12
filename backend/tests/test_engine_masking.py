import re

import pytest

from app.engine.masking import is_masked_aadhaar, is_masked_pan, mask_aadhaar, mask_pan, redact_text

PAN_RAW = re.compile(r"(?!XXXXX)[A-Z]{5}\d{4}[A-Z]", re.I)


def test_mask_pan():
    assert mask_pan("ABCDE1234F") == "XXXXX1234F"
    assert mask_pan("abcde1234f") == "XXXXX1234F"
    assert mask_pan(" ABCDE 1234F ") == "XXXXX1234F"
    assert mask_pan("XXXXX1234F") == "XXXXX1234F"
    assert mask_pan("") == ""
    assert mask_pan(None) == ""
    garbage = mask_pan("1234567890AB")
    assert garbage.startswith("X") and "12345" not in garbage


def test_mask_aadhaar():
    assert mask_aadhaar("1234 5678 9012") == "XXXX XXXX 9012"
    assert mask_aadhaar("123456789012") == "XXXX XXXX 9012"
    assert mask_aadhaar("1234-5678-9012") == "XXXX XXXX 9012"
    assert mask_aadhaar("XXXX XXXX 9012") == "XXXX XXXX 9012"
    assert mask_aadhaar(None) == ""


def test_is_masked():
    assert is_masked_pan("XXXXX1234F") and not is_masked_pan("ABCDE1234F")
    assert is_masked_aadhaar("XXXX XXXX 9012") and not is_masked_aadhaar("1234 5678 9012")


@pytest.mark.parametrize("text,secret", [
    ("PAN: ABCPZ1234F issued", "ABCPZ1234F"),
    ("pan abcpz1234f lower", "abcpz1234f"),
    ("Aadhaar 2345 6789 0123 holder", "2345 6789"),
    ("UID:234567890123.", "23456789"),
    ("Mobile +91 98765 43210 call", "98765"),
    ("Mobile 9876543210", "987654"),
    ("A/c No 50100234567890 HDFC", "501002345"),
])
def test_redact_text_never_leaks(text, secret):
    out = redact_text(text)
    assert secret not in out
    assert not PAN_RAW.search(out)


def test_redact_text_keeps_last4_and_context():
    out = redact_text("Name: Aarav PAN ABCPZ1234F Aadhaar 2345 6789 0123 Mob 9876543210 net pay ₹1,45,000 on 01/10/2026")
    assert "XXXXX1234F" in out
    assert "XXXX XXXX 0123" in out
    assert "XXXXXX3210" in out
    assert "₹1,45,000" in out and "01/10/2026" in out and "Name: Aarav" in out


def test_redact_text_does_not_touch_amounts_ifsc():
    out = redact_text("Loan 4500000 IFSC HDFC0001234 amount 38,626")
    assert out == "Loan 4500000 IFSC HDFC0001234 amount 38,626"


def test_redact_empty():
    assert redact_text("") == "" and redact_text(None) == ""
