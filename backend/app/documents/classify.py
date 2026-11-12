"""Keyword-scoring document classifier (robust to OCR noise: matching ignores spaces/punctuation)."""
from __future__ import annotations

import re

from app.schemas import DocType

# (phrase, weight). Phrases are matched on a squashed form: lower-case letters/digits only.
_KEYWORDS: dict[DocType, list[tuple[str, float]]] = {
    DocType.PAN: [("permanent account number", 6), ("income tax department", 3), ("father's name", 1.5),
                  ("pan card", 2)],
    DocType.AADHAAR: [("aadhaar", 5), ("unique identification authority", 5), ("government of india", 1.5),
                      ("aam aadmi ka adhikar", 3), ("vid", 0.2), ("enrolment no", 2)],
    DocType.SALARY_SLIP: [("payslip", 5), ("pay slip", 5), ("salary slip", 5), ("net pay", 3), ("earnings", 1.5),
                          ("deductions", 1), ("gross earnings", 2), ("provident fund", 1), ("employee id", 1.5)],
    DocType.FORM16: [("form no 16", 6), ("form 16", 4), ("section 203", 3), ("tan of the deductor", 3),
                     ("income chargeable under the head salaries", 3), ("standard deduction", 1)],
    DocType.ITR: [("income tax return acknowledgement", 7), ("itr v", 3), ("acknowledgement number", 3),
                  ("gross total income", 1.5), ("taxes paid", 1.5), ("form number", 1), ("date of filing", 2)],
    DocType.BANK_STATEMENT: [("statement of account", 5), ("account statement", 4), ("opening balance", 3),
                             ("closing balance", 2), ("narration", 2), ("withdrawal", 1.5), ("deposit", 1),
                             ("value dt", 1.5)],
    DocType.SALE_DEED: [("sale deed", 5), ("agreement for sale", 6), ("conveyance", 3), ("title deed", 5),
                        ("vendor", 1.5), ("purchaser", 1.5), ("sub registrar", 2), ("schedule of property", 3),
                        ("stamp duty", 1.5), ("witnesseth", 2)],
    DocType.VALUATION_REPORT: [("valuation report", 6), ("fair market value", 3), ("distress value", 3),
                               ("realisable value", 2), ("valuer", 1.5), ("date of inspection", 1.5)],
}
_FILENAME_HINTS: dict[DocType, tuple[str, ...]] = {
    DocType.PAN: ("pan",), DocType.AADHAAR: ("aadhaar", "aadhar", "uidai"),
    DocType.SALARY_SLIP: ("salary", "payslip", "slip"), DocType.FORM16: ("form16", "form_16", "form-16"),
    DocType.ITR: ("itr",), DocType.BANK_STATEMENT: ("statement", "bank"),
    DocType.SALE_DEED: ("deed", "agreement", "sale"), DocType.VALUATION_REPORT: ("valuation", "valuer"),
}


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def classify(text: str, filename: str = "") -> tuple[DocType, float]:
    """Return (doc_type, confidence 0..1)."""
    sq = squash(text)
    scores: dict[DocType, float] = {}
    for dt, kws in _KEYWORDS.items():
        s = 0.0
        for phrase, w in kws:
            n = sq.count(squash(phrase))
            if n:
                s += w * min(n, 3) ** 0.5
        scores[dt] = s
    if re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", text) and scores[DocType.PAN] > 0:
        scores[DocType.PAN] += 2
    if re.search(r"X{4}\s?X{4}\s?\d{4}", text, re.I):
        scores[DocType.AADHAAR] += 2
    fname = filename.lower()
    for dt, hints in _FILENAME_HINTS.items():
        if any(h in fname for h in hints):
            scores[dt] += 1.0
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, top = ranked[0]
    second = ranked[1][1]
    if top < 3.0:
        return DocType.UNKNOWN, round(min(top / 3.0, 1.0) * 0.5, 2)
    conf = top / (top + second) if top + second else 0.0
    conf = min(0.99, 0.5 + 0.5 * conf) if top >= 6 else min(0.9, conf)
    return best, round(conf, 2)
