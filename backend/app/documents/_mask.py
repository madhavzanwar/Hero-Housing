"""PII masking for the document layer.

Delegates to :mod:`app.engine.masking` (single implementation for the whole app) and adds an
OCR-tolerant pass: OCR may misread one character of a PAN (``ABCPZ1Z34F``), which the strict
regex would miss, so 10-character PAN-shaped tokens with digit/letter confusions are masked too.
"""
from __future__ import annotations

import re

try:  # pragma: no cover - import path depends on engine module being present
    from app.engine.masking import mask_aadhaar, mask_pan
    from app.engine.masking import redact_text as _redact
except Exception:  # pragma: no cover
    _PAN = re.compile(r"\b([A-Za-z]{5})(\d{4})([A-Za-z])\b")
    _AAD = re.compile(r"(?<![\dA-Za-z])(\d{4})[ \-]?(\d{4})[ \-]?(\d{4})(?![\dA-Za-z])")
    _LONG = re.compile(r"(?<![\dA-Za-z])\d{9,18}(?![\dA-Za-z])")

    def mask_pan(s: str | None) -> str:
        v = re.sub(r"\s", "", str(s or "")).upper()
        return f"XXXXX{v[5:9]}{v[9:10]}" if len(v) == 10 else ("X" * max(len(v) - 4, 0) + v[-4:])

    def mask_aadhaar(s: str | None) -> str:
        d = re.sub(r"\D", "", str(s or ""))
        return f"XXXX XXXX {d[-4:]}" if len(d) >= 4 else "XXXX XXXX XXXX"

    def _redact(text: str | None) -> str:
        out = _PAN.sub(lambda m: f"XXXXX{m.group(2)}{m.group(3).upper()}", str(text or ""))
        out = _AAD.sub(lambda m: f"XXXX XXXX {m.group(3)}", out)
        return _LONG.sub(lambda m: "X" * (len(m.group(0)) - 4) + m.group(0)[-4:], out)

# PAN-shaped token allowing common OCR confusions (O/0, I/1, S/5, B/8, Z/2) in either half.
_FUZZY_PAN = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{3}[PCHFATBLJG][A-Z0-9])([0-9OIlSBZ]{4})([A-Z0-9])(?![A-Za-z0-9])")


def _fuzzy_pan_sub(m: re.Match[str]) -> str:
    head, digits, tail = m.group(1), m.group(2), m.group(3)
    letters = sum(c.isalpha() for c in head)
    if letters < 4 or head.startswith("XXXX"):
        return m.group(0)
    return f"XXXXX{digits}{tail}"


def redact_text(text: str | None) -> str:
    """Mask PAN / Aadhaar / mobile / long digit runs, tolerant to OCR noise."""
    return _FUZZY_PAN.sub(_fuzzy_pan_sub, _redact(text))


__all__ = ["mask_aadhaar", "mask_pan", "redact_text"]
