"""Compliance & KYC checks: required documents, PAN, Aadhaar masking, cross-document consistency,
CERSAI / encumbrance, LAP end-use, title documents, valuation variance and disclosure (KFS / FPC) rules.
"""
from __future__ import annotations

import re
from typing import Any

from app.engine.finance import fmt_inr, pct
from app.engine.fraud import name_similarity
from app.engine.masking import is_masked_aadhaar, is_masked_pan
from app.engine.rules import hit
from app.policy.loader import Policy
from app.schemas import (
    ApplicationForm,
    DocType,
    DocumentBundle,
    EmploymentType,
    Product,
    RuleHit,
    RuleOutcome,
    Severity,
)

OC = RuleOutcome
S = Severity
_NIL_RE = re.compile(r"^\s*(nil|none|no\b|not encumbered|free from|clear|no encumbrance|no charge)", re.I)
_PROHIBITED_HINTS = {
    "Capital market investment": ["stock market", "stock trading", "stocks", "share market",
                                  "share trading", "equity", "capital market", "f&o", "derivative",
                                  "intraday", "mutual fund"],
    "Speculation": ["speculat"],
    "Purchase of land for speculation": ["land banking"],
    "Gold/bullion": ["gold", "bullion"],
    "Chit funds": ["chit"],
    "Crypto assets": ["crypto", "bitcoin"],
}
_DOC_LABEL = {
    DocType.PAN: "PAN card", DocType.AADHAAR: "Aadhaar", DocType.SALARY_SLIP: "salary slips",
    DocType.FORM16: "Form 16", DocType.ITR: "ITR", DocType.BANK_STATEMENT: "bank statement",
    DocType.SALE_DEED: "sale deed / title deed", DocType.VALUATION_REPORT: "valuation report",
}


def classify_end_use(end_use: str, policy: Policy) -> tuple[str, str]:
    """Return ('PROHIBITED'|'ALLOWED'|'UNCLEAR', matched category)."""
    eu = end_use.lower().strip()
    for cat in policy.get("lap.prohibited_end_uses", []):
        hints = [cat.lower(), *_PROHIBITED_HINTS.get(cat, [])]
        if any(h in eu for h in hints):
            return "PROHIBITED", cat
    for cat in policy.get("lap.allowed_end_uses", []):
        c = cat.lower()
        if c in eu or eu in c or (c.split()[0] in eu and len(c.split()[0]) > 4):
            return "ALLOWED", cat
    return "UNCLEAR", ""


def run(form: ApplicationForm, bundle: DocumentBundle, policy: Policy) -> list[RuleHit]:
    hits: list[RuleHit] = []
    kyc = policy.section("kyc")
    emp = form.employment_type.value
    present = {d.doc_type for d in bundle.documents}
    required = [DocType(x) for x in kyc.get("required_documents", {}).get(emp, [])]
    missing = [d for d in required if d not in present] + [d for d in bundle.missing_documents if d not in present]
    missing = list(dict.fromkeys(missing))
    n_slips = max(len(bundle.salary_slips), sum(1 for d in bundle.documents if d.doc_type == DocType.SALARY_SLIP))
    min_slips = int(kyc.get("min_salary_slips", 3))
    short_slips = form.employment_type == EmploymentType.SALARIED and DocType.SALARY_SLIP in present and n_slips < min_slips

    # PAN
    pan = bundle.identity.get("pan_masked")
    if DocType.PAN not in present and not pan:
        hits.append(hit(policy, "KYC-PAN-01", OC.FAIL, "PAN card not provided; PAN (or Form 60) is mandatory for a home loan.",
                        effect="REFER", severity=S.HIGH, evidence={"condition": "SUBMIT_DOC"}))
    else:
        hits.append(hit(policy, "KYC-PAN-01", OC.PASS, f"PAN captured ({pan or 'masked'}).", evidence={"pan_masked": pan}))
        if pan and not is_masked_pan(str(pan)):
            hits.append(hit(policy, "KYC-PAN-01", OC.WARN, "PAN was not stored in masked form; masked before persistence.",
                            severity=S.MEDIUM))
    # Aadhaar
    aad = bundle.identity.get("aadhaar_masked")
    if aad and not is_masked_aadhaar(str(aad)):
        hits.append(hit(policy, "KYC-AAD-01", OC.FAIL,
                        "Aadhaar number is not masked to the last 4 digits; it must be masked before storage.",
                        severity=S.HIGH))
    elif aad:
        hits.append(hit(policy, "KYC-AAD-01", OC.PASS, f"Aadhaar stored masked ({aad}).", evidence={"aadhaar_masked": aad}))
    # required documents
    other_missing = [d for d in missing if d != DocType.PAN]
    if other_missing or short_slips:
        parts = [_DOC_LABEL.get(d, d.value) for d in other_missing]
        if short_slips:
            parts.append(f"{min_slips - n_slips} more salary slip(s) (have {n_slips}, need {min_slips})")
        hits.append(hit(policy, "KYC-DOC-01", OC.WARN, "Documents still required: " + ", ".join(parts) + ".",
                        effect="CONDITION", severity=S.MEDIUM,
                        evidence={"missing": [d.value for d in other_missing], "salary_slips": n_slips,
                                  "condition": "SUBMIT_DOC", "items": parts}))
    else:
        hits.append(hit(policy, "KYC-DOC-01", OC.PASS, f"All {len(required)} required documents received.",
                        evidence={"required": [d.value for d in required]}))

    # cross-document consistency
    for cc in bundle.cross_checks:
        if cc.match or cc.field == "salary_vs_credit":
            continue
        vals = {k: v for k, v in cc.values.items()}
        if cc.field in ("name", "dob", "pan"):
            hits.append(hit(policy, "KYC-XCHK-01", OC.FAIL,
                            f"{cc.field.upper() if cc.field != 'name' else 'Name'} differs across documents"
                            f" (similarity {cc.score:.2f}). {cc.note}".strip(),
                            effect="REFER", severity=S.HIGH, evidence={"field": cc.field, "values": vals, "score": cc.score}))
        else:
            hits.append(hit(policy, "KYC-XCHK-01", OC.WARN,
                            (f"{cc.field.replace('_', ' ').capitalize()} differs across documents "
                             f"(similarity {cc.score:.2f}). {cc.note}").strip(),
                            effect="CONDITION", severity=S.LOW,
                            evidence={"field": cc.field, "values": vals, "score": cc.score, "condition": "SUBMIT_DOC"}))
    if bundle.cross_checks and all(c.match for c in bundle.cross_checks):
        hits.append(hit(policy, "KYC-XCHK-01", OC.PASS,
                        f"{len(bundle.cross_checks)} cross-document checks consistent (name, DOB, employer, address)."))

    prop = bundle.property or {}
    # CERSAI / encumbrance
    enc = prop.get("encumbrance")
    if enc is None or str(enc).strip() == "":
        hits.append(hit(policy, "CMP-CERSAI-01", OC.WARN,
                        "Encumbrance status not available; CERSAI search and legal clearance required before disbursal.",
                        effect="CONDITION", severity=S.MEDIUM, evidence={"condition": "LEGAL_TITLE"}))
    elif _NIL_RE.match(str(enc)):
        hits.append(hit(policy, "CMP-CERSAI-01", OC.PASS, "Property is free of recorded encumbrances (search shows NIL).",
                        evidence={"encumbrance": enc}))
    else:
        hits.append(hit(policy, "CMP-CERSAI-01", OC.FAIL,
                        f"An existing charge is recorded on the property ('{str(enc)[:120]}'); it must be released or "
                        f"taken over before a mortgage can be created.",
                        effect="REFER", severity=S.HIGH, evidence={"encumbrance": enc, "condition": "LEGAL_TITLE"}))

    # title documents
    if DocType.SALE_DEED not in present:
        hits.append(hit(policy, "CMP-LEGAL-01", OC.WARN,
                        "Sale deed / agreement for sale not provided; title cannot be verified.",
                        effect="CONDITION", severity=S.MEDIUM, evidence={"condition": "LEGAL_TITLE"}))
    elif form.product == Product.LAP and prop.get("owner"):
        owners = str(prop["owner"])
        names = [form.applicant_name] + ([form.co_applicant.name] if form.co_applicant else [])
        best = max(name_similarity(n, owners) for n in names)
        best = max(best, max(name_similarity(n, part) for n in names for part in re.split(r",|&| and ", owners) if part.strip()))
        if best < float(policy.get("fraud.name_match_threshold", 0.85)):
            hits.append(hit(policy, "CMP-LEGAL-01", OC.FAIL,
                            f"Title deed is in the name of '{owners}', not the applicant; the owner must join as co-borrower.",
                            effect="REFER", severity=S.HIGH, evidence={"owner": owners, "score": round(best, 2)}))
        else:
            hits.append(hit(policy, "CMP-LEGAL-01", OC.PASS, "Title deed is in the applicant's name.",
                            evidence={"owner": owners}))
    else:
        hits.append(hit(policy, "CMP-LEGAL-01", OC.PASS, "Sale deed / agreement for sale received for legal vetting.",
                        evidence={"registration_no": prop.get("registration_no")}))

    # valuation variance
    valuation = float(prop.get("market_value") or 0)
    agreement = float(prop.get("consideration_value") or 0) or float(form.property_value)
    var_ref = float(policy.get("ltv.valuation_variance_refer", 0.15))
    if valuation > 0 and agreement > 0:
        var = abs(agreement - valuation) / max(agreement, valuation)
        ev: dict[str, Any] = {"agreement_value": agreement, "valuation": valuation, "variance": round(var, 4)}
        label = "Declared" if form.product == Product.LAP else "Agreement"
        if var > var_ref:
            hits.append(hit(policy, "CMP-VAL-01", OC.WARN,
                            f"{label} value {fmt_inr(agreement)} differs from the technical valuation {fmt_inr(valuation)} by "
                            f"{pct(var)} (limit {pct(var_ref, 0)}); a second valuation is required.",
                            effect="REFER", severity=S.MEDIUM, evidence=ev))
        else:
            hits.append(hit(policy, "CMP-VAL-01", OC.PASS,
                            f"{label} value and technical valuation differ by {pct(var)}, within {pct(var_ref, 0)}.",
                            evidence=ev))

    # LAP end use
    if form.product == Product.LAP:
        eu = (form.lap_end_use or "").strip()
        if not eu:
            hits.append(hit(policy, "CMP-LAP-01", OC.WARN, "End use of LAP funds not declared.",
                            effect="CONDITION", severity=S.MEDIUM, evidence={"condition": "END_USE_DECLARATION"}))
        else:
            status, cat = classify_end_use(eu, policy)
            if status == "PROHIBITED":
                hits.append(hit(policy, "CMP-LAP-01", OC.FAIL,
                                f"Declared end use '{eu}' falls under the prohibited category '{cat}'; LAP funds cannot be "
                                f"used for speculative or capital-market purposes.",
                                effect="DECLINE", severity=S.CRITICAL, evidence={"end_use": eu, "category": cat}))
            elif status == "ALLOWED":
                hits.append(hit(policy, "CMP-LAP-01", OC.PASS, f"Declared end use '{eu}' is permitted ({cat}).",
                                evidence={"end_use": eu, "category": cat}))
            else:
                hits.append(hit(policy, "CMP-LAP-01", OC.WARN,
                                f"Declared end use '{eu}' is not a standard permitted category; an end-use declaration "
                                f"and utilisation certificate are required.",
                                effect="CONDITION", severity=S.MEDIUM,
                                evidence={"end_use": eu, "condition": "END_USE_DECLARATION"}))

    # disclosures (informational, always cited)
    hits.append(hit(policy, "CMP-KFS-01", OC.INFO,
                    "A Key Facts Statement with the annual percentage rate and all fees will accompany the sanction letter."))
    hits.append(hit(policy, "CMP-FPC-01", OC.INFO,
                    "Sanction terms, or written reasons in case of rejection, are communicated to the applicant."))
    if form.rate_type == "FLOATING":
        hits.append(hit(policy, "CMP-PREPAY-01", OC.INFO,
                        "Floating-rate loan to an individual: no foreclosure or prepayment charges apply."
                        if form.product == Product.HOME_LOAN else
                        "Floating-rate loan: prepayment terms disclosed in the KFS."))
    return hits
