"""Shared helpers for the document-layer tests (imported by test_documents_*.py)."""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from app.documents.pipeline import process_documents
from app.schemas import ApplicationForm, DocumentBundle

PERSONA_DIR = Path(__file__).resolve().parents[2] / "data" / "personas"
PERSONA_IDS = [f"p{i:02d}" for i in range(1, 13)]
COUNT_KEYS = {"salary_credits": ("SALARY", 1), "bounces": ("BOUNCE", 0), "gambling_txns": ("GAMBLING", -1),
              "cash_deposits": ("CASH_DEPOSIT", 1), "emi_debits": ("EMI", -1)}


def persona_files(pid: str) -> list[tuple[str, bytes]]:
    return [(f.name, f.read_bytes()) for f in sorted((PERSONA_DIR / pid).iterdir()) if f.suffix in (".pdf", ".png")]


def persona_form(pid: str) -> ApplicationForm:
    data = json.loads((PERSONA_DIR / pid / "application.json").read_text())
    data.pop("persona", None)
    return ApplicationForm(**data)


def expected(pid: str) -> dict[str, Any]:
    return json.loads((PERSONA_DIR / pid / "expected.json").read_text())


@cache
def bundle_for(pid: str) -> DocumentBundle:
    """Process each persona once per test session (OCR is the slow part)."""
    return process_documents(persona_files(pid), persona_form(pid))


def squash(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v).upper())


def values_match(got: Any, exp: Any, ocr: bool) -> bool:
    if isinstance(exp, (int, float)) and not isinstance(exp, bool):
        return isinstance(got, (int, float)) and abs(float(got) - float(exp)) <= max(1.0, abs(exp) * 1e-6)
    if got is None:
        return False
    a, b = squash(got), squash(exp)
    if a == b:
        return True
    if ocr:  # OCR may drop spaces or garble one or two characters
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a, b).ratio() >= 0.9
    return False
