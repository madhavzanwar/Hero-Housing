"""PII masking (DPDP Act 2023 data minimisation; Aadhaar Act s.29 - only last 4 digits).

`mask_pan("ABCDE1234F") -> "XXXXX1234F"`; `mask_aadhaar("1234 5678 9012") -> "XXXX XXXX 9012"`;
`redact_text(text)` masks PAN, Aadhaar, mobile numbers and long digit runs (account numbers)
anywhere in free text.
"""
from __future__ import annotations

import re

_PAN_RE = re.compile(r"\b([A-Za-z]{5})(\d{4})([A-Za-z])\b")
# 12 digits, optionally grouped 4-4-4 with spaces or hyphens; first digit 2-9 per UIDAI, but accept any
_AADHAAR_RE = re.compile(r"(?<![\dA-Za-z])(\d{4})[ \-]?(\d{4})[ \-]?(\d{4})(?![\dA-Za-z])")
# Indian mobile: optional +91 / 91 / 0 prefix, 10 digits starting 6-9 (allow one space/hyphen after 5 digits)
_MOBILE_RE = re.compile(r"(?<![\dA-Za-z])(?:\+?91[ \-]?|0)?([6-9]\d{4})[ \-]?(\d{5})(?![\dA-Za-z])")
# Any other long digit run (bank account numbers, card numbers, UPI refs): 9-18 digits
_LONG_DIGITS_RE = re.compile(r"(?<![\dA-Za-z])\d{9,18}(?![\dA-Za-z])")
_MASKED_PAN_RE = re.compile(r"^X{5}\d{4}[A-Z]$")
_MASKED_AADHAAR_RE = re.compile(r"^X{4} ?X{4} ?\d{4}$")


def mask_pan(s: str | None) -> str:
    """Keep the 4 digits and the check letter: ``ABCDE1234F`` -> ``XXXXX1234F``.
    Already-masked or malformed values are masked defensively (last 5 chars kept at most)."""
    if not s:
        return ""
    v = re.sub(r"\s", "", str(s)).upper()
    m = re.fullmatch(r"[A-Z]{5}(\d{4})([A-Z])", v)
    if m:
        return f"XXXXX{m.group(1)}{m.group(2)}"
    if _MASKED_PAN_RE.match(v):
        return v
    tail = v[-5:] if len(v) > 5 else v[-1:]
    return "X" * max(len(v) - len(tail), 5) + tail


def mask_aadhaar(s: str | None) -> str:
    """``1234 5678 9012`` -> ``XXXX XXXX 9012`` (only last 4 digits retained)."""
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))
    if len(digits) >= 4:
        return f"XXXX XXXX {digits[-4:]}"
    return "XXXX XXXX XXXX"


def is_masked_pan(s: str | None) -> bool:
    return bool(s) and bool(_MASKED_PAN_RE.match(str(s).replace(" ", "").upper()))


def is_masked_aadhaar(s: str | None) -> bool:
    return bool(s) and bool(_MASKED_AADHAAR_RE.match(str(s).strip().upper()))


def mask_mobile(s: str | None) -> str:
    digits = re.sub(r"\D", "", str(s or ""))
    return f"XXXXXX{digits[-4:]}" if len(digits) >= 4 else "XXXXXXXXXX"


def redact_text(text: str | None) -> str:
    """Mask every PAN / Aadhaar / mobile / long account-number pattern in free text."""
    if not text:
        return ""
    out = _PAN_RE.sub(lambda m: f"XXXXX{m.group(2)}{m.group(3).upper()}", str(text))
    out = _AADHAAR_RE.sub(lambda m: f"XXXX XXXX {m.group(3)}", out)
    out = _MOBILE_RE.sub(lambda m: f"XXXXXX{m.group(2)[-4:]}", out)
    out = _LONG_DIGITS_RE.sub(lambda m: "X" * (len(m.group(0)) - 4) + m.group(0)[-4:], out)
    return out
