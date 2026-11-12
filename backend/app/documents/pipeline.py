"""Document layer entry point: ``process_documents(files, form) -> DocumentBundle``.

Steps per file: sniff type -> extract text (pypdf text layer; OCR for images / image-only PDFs) ->
classify -> parse fields -> mask PII immediately -> tamper heuristics. Then bundle-level steps:
identity / income / property aggregation, cross-document checks, duplicate detection and
missing-document check against ``policy.kyc.required_documents``.

PII rule: full PAN / Aadhaar numbers exist only transiently inside this module; every value placed
in the returned bundle is masked (``XXXXX1234F`` / ``XXXX XXXX 1234``) and free text is redacted.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from statistics import mean
from typing import Any

from app.documents import crosscheck as cc
from app.documents import ocr, tamper
from app.documents import parsers as P  # noqa: N812
from app.documents._mask import mask_aadhaar, mask_pan, redact_text
from app.documents.classify import classify
from app.documents.extract import RawContent, extract, sniff_mime
from app.schemas import (
    ApplicationForm,
    DocType,
    DocumentBundle,
    DocumentResult,
    EmploymentType,
    ExtractedField,
    Flag,
    Severity,
    Transaction,
)

_DEFAULT_REQUIRED = {
    "SALARIED": ["PAN", "AADHAAR", "SALARY_SLIP", "BANK_STATEMENT", "FORM16", "SALE_DEED", "VALUATION_REPORT"],
    "SELF_EMPLOYED": ["PAN", "AADHAAR", "ITR", "BANK_STATEMENT", "SALE_DEED", "VALUATION_REPORT"],
}


def _policy_get(key: str, default: Any) -> Any:
    try:
        from app.policy.loader import get_policy

        val = get_policy().get(key, default)
        return default if val is None else val
    except Exception:  # policy module unavailable: fall back to defaults
        return default


def _parse(doc_type: DocType, text: str) -> dict[str, Any]:
    if doc_type == DocType.PAN:
        return P.parse_pan_card(text)
    if doc_type == DocType.AADHAAR:
        return P.parse_aadhaar(text)
    if doc_type == DocType.SALARY_SLIP:
        return P.parse_salary_slip(text)
    if doc_type == DocType.FORM16:
        return P.parse_form16(text)
    if doc_type == DocType.ITR:
        return P.parse_itr(text)
    if doc_type == DocType.SALE_DEED:
        return P.parse_sale_deed(text)
    if doc_type == DocType.VALUATION_REPORT:
        return P.parse_valuation(text)
    return {}


def _jsonable(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        return redact_text(v)
    return v


def _fields(parsed: dict[str, Any], source: str, conf: float) -> list[ExtractedField]:
    out = []
    for k, v in parsed.items():
        if k.startswith("_") or v is None or v == "":
            continue
        out.append(ExtractedField(name=k, value=_jsonable(v), confidence=round(conf, 2), source=source))
    if parsed.get("_pan_full"):
        out.append(ExtractedField(name="pan_masked", value=mask_pan(parsed["_pan_full"]), confidence=round(conf, 2),
                                  source=source))
    if parsed.get("aadhaar_last4"):
        out.append(ExtractedField(name="aadhaar_masked", value=mask_aadhaar(parsed["aadhaar_last4"]),
                                  confidence=round(conf, 2), source=source))
    return out


def _excerpt(text: str) -> str:
    t = re.sub(r"[ \t]{2,}", "  ", text)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return redact_text(t)[:600]


def _months_covered(txns: list[Transaction]) -> float:
    if not txns:
        return 0.0
    days = (txns[-1].date - txns[0].date).days + 1
    return round(days / 30.44, 1)


def process_documents(files: list[tuple[str, bytes]], form: ApplicationForm | None = None) -> DocumentBundle:
    suspicious = _policy_get("fraud.suspicious_pdf_producers", None)
    name_threshold = float(_policy_get("fraud.name_match_threshold", 0.85))
    round_share = float(_policy_get("fraud.round_number_share", 0.6))
    required = _policy_get("kyc.required_documents", _DEFAULT_REQUIRED)
    min_slips = int(_policy_get("kyc.min_salary_slips", 3))

    bundle = DocumentBundle()
    parsed_docs: list[tuple[DocumentResult, dict[str, Any], RawContent]] = []
    statements: dict[str, list[Transaction]] = {}

    # OCR all images up front, concurrently (results land in the in-memory + disk OCR cache)
    images = [data for name, data in files if sniff_mime(name, data).startswith("image/")]
    if images:
        ocr.warm(images)

    for idx, (filename, data) in enumerate(files):
        sha = hashlib.sha256(data).hexdigest()
        doc_id = f"doc-{idx + 1:02d}-{sha[:8]}"
        raw = extract(filename, data)
        doc_type, conf = classify(raw.text, filename)
        parsed: dict[str, Any] = {}
        txns: list[Transaction] = []
        if doc_type == DocType.BANK_STATEMENT:
            meta, txns = P.parse_bank_statement(raw.text)
            parsed = {
                "bank_name": meta.get("bank_name"), "account_holder": meta.get("account_holder"),
                "account_no_masked": ("XXXXXXXX" + re.sub(r"\D", "", meta["account_no"])[-4:])
                if meta.get("account_no") else None,
                "ifsc": meta.get("ifsc"), "address": meta.get("address"),
                "period_start": meta.get("period_start"), "period_end": meta.get("period_end"),
                "opening_balance": meta.get("opening_balance"), "closing_balance": meta.get("closing_balance"),
                "n_transactions": len(txns), "months_covered": _months_covered(txns),
                "total_credits": round(sum(t.amount for t in txns if t.amount > 0), 2),
                "total_debits": round(-sum(t.amount for t in txns if t.amount < 0), 2),
            }
            txns = [t.model_copy(update={"description": redact_text(t.description)}) for t in txns]
            statements[doc_id] = txns
            bundle.transactions.extend(txns)
        else:
            parsed = _parse(doc_type, raw.text)
        field_conf = raw.confidence if raw.source == "ocr" else 0.99
        source = "ocr" if raw.source == "ocr" else "text"
        metadata: dict[str, Any] = {**raw.metadata, "source": raw.source, "sha256": sha,
                                    "text_chars": len(raw.text)}
        if raw.source == "ocr":
            metadata["ocr_confidence"] = raw.confidence
        if raw.notes:
            metadata["notes"] = raw.notes
        res = DocumentResult(
            id=doc_id, filename=filename, doc_type=doc_type, mime_type=raw.mime_type, pages=raw.pages,
            ocr_engine=raw.engine if raw.source != "text" else "pdf-text",
            classification_confidence=conf, fields=_fields(parsed, source, field_conf),
            text_excerpt=_excerpt(raw.text), sha256=sha, metadata=metadata)

        # ---- per-document tamper heuristics
        flags: list[Flag] = []
        if len(raw.text.strip()) < 30:
            flags.append(Flag(code="DOC_UNREADABLE", severity=Severity.MEDIUM, document_id=doc_id,
                              title="Document could not be read",
                              detail=f"No text could be extracted from '{filename}' (OCR engine: {raw.engine}). "
                                     "Ask for a clearer copy or the original PDF.",
                              evidence={"ocr_engine": raw.engine, "notes": raw.notes}))
        if raw.mime_type == "application/pdf":
            flags += tamper.metadata_flags(doc_id, doc_type, raw.metadata, suspicious)
            flags += tamper.font_flags(doc_id, doc_type, raw.amount_fonts, raw.metadata.get("font_runs"))
        if doc_type == DocType.SALARY_SLIP:
            flags += tamper.slip_flags(doc_id, parsed)
        if doc_type == DocType.BANK_STATEMENT:
            flags += tamper.statement_round_flag(doc_id, txns, round_share)
        flags += tamper.composite_flag(doc_id, doc_type, flags)
        res.flags = flags
        bundle.flags.extend(flags)
        bundle.documents.append(res)
        parsed_docs.append((res, parsed, raw))

    _aggregate(bundle, parsed_docs, form, name_threshold)
    bundle.flags.extend(tamper.duplicate_flags([(d.id, d.filename, d.doc_type, d.sha256) for d in bundle.documents],
                                               statements))

    # ---- completeness
    present = {d.doc_type for d in bundle.documents}
    if form is not None:
        emp = form.employment_type.value
    else:
        emp = EmploymentType.SELF_EMPLOYED.value if DocType.ITR in present and DocType.SALARY_SLIP not in present \
            else EmploymentType.SALARIED.value
    req = [DocType(x) for x in (required.get(emp) or _DEFAULT_REQUIRED[emp])]
    bundle.missing_documents = [d for d in req if d not in present]
    n_slips = sum(1 for d in bundle.documents if d.doc_type == DocType.SALARY_SLIP)
    if emp == EmploymentType.SALARIED.value and 0 < n_slips < min_slips:
        bundle.flags.append(Flag(code="INSUFFICIENT_SALARY_SLIPS", severity=Severity.LOW,
                                 title="Fewer salary slips than required",
                                 detail=f"{n_slips} salary slip(s) received; policy requires the latest {min_slips}.",
                                 evidence={"received": n_slips, "required": min_slips}))
    bundle.transactions.sort(key=lambda t: t.date)
    return bundle


def _aggregate(bundle: DocumentBundle, parsed_docs: list[tuple[DocumentResult, dict[str, Any], RawContent]],
               form: ApplicationForm | None, name_threshold: float) -> None:
    by_type: dict[DocType, list[tuple[DocumentResult, dict[str, Any]]]] = {}
    for res, parsed, _raw in parsed_docs:
        by_type.setdefault(res.doc_type, []).append((res, parsed))

    def first(dt: DocType) -> tuple[DocumentResult | None, dict[str, Any]]:
        lst = by_type.get(dt) or []
        return (lst[0][0], lst[0][1]) if lst else (None, {})

    # vocabulary for re-spacing OCR-glued names
    vocab: set[str] = set()
    for _res, parsed, raw in parsed_docs:
        if raw.source == "text":
            for key in ("employee_name", "account_holder", "name", "owner"):
                if parsed.get(key):
                    vocab.update(cc.norm_name(str(parsed[key])).split())
    if form:
        vocab.update(cc.norm_name(form.applicant_name).split())
    for _res, parsed, raw in parsed_docs:
        if raw.source == "ocr":
            for key in ("name", "father_name", "employee_name", "owner"):
                if parsed.get(key):
                    fixed = cc.resegment(parsed[key], vocab)
                    if fixed != parsed[key]:
                        parsed[key] = fixed
                        for f in _res.fields:
                            if f.name == key:
                                f.value = fixed

    pan_res, pan = first(DocType.PAN)
    _aad_res, aad = first(DocType.AADHAAR)
    stmt_res, _ = first(DocType.BANK_STATEMENT)
    stmt = {f.name: f.value for f in stmt_res.fields} if stmt_res else {}

    # ---- identity
    name = pan.get("name") or aad.get("name") or (form.applicant_name if form else None)
    if name and pan_res is not None and pan_res.metadata.get("source") == "ocr":
        # OCR may garble a letter; prefer the same name read from a text-layer document when it agrees
        text_names = [p.get(k) for r, p, raw in parsed_docs if raw.source == "text"
                      for k in ("account_holder", "employee_name", "name") if p.get(k)]
        best = max(text_names, key=lambda n: cc.name_similarity(n, name), default=None)
        if best and cc.name_similarity(best, name) >= 0.85 and len(str(best).split()) >= len(str(name).split()):
            name = best
    dob: date | None = pan.get("dob") or aad.get("dob")
    bundle.identity = {k: v for k, v in {
        "name": name.title() if isinstance(name, str) and name.isupper() else name,
        "dob": dob.isoformat() if dob else None,
        "pan_masked": mask_pan(pan["_pan_full"]) if pan.get("_pan_full") else None,
        "aadhaar_masked": mask_aadhaar(aad["aadhaar_last4"]) if aad.get("aadhaar_last4") else None,
        "aadhaar_masked_on_document": aad.get("aadhaar_was_masked_on_doc"),
        "address": redact_text(aad.get("address")) if aad.get("address") else None,
        "pincode": aad.get("pincode"),
        "gender": aad.get("gender"),
        "father_name": pan.get("father_name"),
    }.items() if v is not None}

    # ---- salary slips
    for res, s in sorted(by_type.get(DocType.SALARY_SLIP, []), key=lambda x: x[1].get("month") or ""):
        bundle.salary_slips.append({"month": s.get("month"), "gross": s.get("gross"), "net": s.get("net_pay"),
                                    "total_deductions": s.get("total_deductions"), "employer": s.get("employer"),
                                    "document_id": res.id})

    # ---- income docs
    f16_res, f16 = first(DocType.FORM16)
    itrs = sorted([p for _r, p in by_type.get(DocType.ITR, [])], key=lambda p: p.get("ay") or "")
    if f16_res:
        bundle.income_docs = {"type": "FORM16", "annual_income": f16.get("gross_salary"),
                              "taxable_income": f16.get("taxable_income"), "tax": f16.get("tax"),
                              "employer": f16.get("employer"), "ay": f16.get("ay"), "document_id": f16_res.id}
    elif itrs:
        years = [{"ay": p.get("ay"), "total_income": p.get("total_income"),
                  "gross_total_income": p.get("gross_total_income"), "tax_paid": p.get("tax_paid"),
                  "form": p.get("form")} for p in itrs]
        incomes = [y["total_income"] for y in years if y["total_income"]]
        bundle.income_docs = {"type": "ITR", "years": years,
                              "annual_income": round(mean(incomes), 2) if incomes else None,
                              "latest_annual_income": incomes[-1] if incomes else None,
                              "ay": years[-1]["ay"], "employer": form.employer_or_business if form else None}

    # ---- property
    deed_res, deed = first(DocType.SALE_DEED)
    _val_res, val = first(DocType.VALUATION_REPORT)
    prop = {
        "address": deed.get("property_address") or val.get("property_address"),
        "market_value": val.get("market_value"), "distress_value": val.get("distress_value"),
        "realisable_value": val.get("realisable_value"), "guideline_value": val.get("guideline_value"),
        "area_sqft": val.get("area_sqft") or deed.get("area_sqft"),
        "owner": deed.get("owner") or val.get("owner"), "registration_no": deed.get("registration_no"),
        "registration_date": deed["registration_date"].isoformat() if deed.get("registration_date") else None,
        "consideration_value": deed.get("consideration_value"), "deed_type": deed.get("deed_type"),
        "encumbrance": deed.get("encumbrance") if deed_res else None,
        "valuation_date": val["inspection_date"].isoformat() if val.get("inspection_date") else None,
        "valuer": val.get("valuer"),
    }
    bundle.property = {k: v for k, v in prop.items() if v is not None}

    # ---- cross checks
    checks: list[tuple[Any, list[Flag]]] = []
    names: dict[str, str | None] = {"pan": pan.get("name"), "aadhaar": aad.get("name"),
                                       "bank_statement": stmt.get("account_holder")}
    for i, (_r, s) in enumerate(by_type.get(DocType.SALARY_SLIP, [])):
        names[f"salary_slip_{s.get('month') or i + 1}"] = s.get("employee_name")
    names["form16"] = f16.get("employee_name")
    for p in itrs:
        names[f"itr_{p.get('ay')}"] = p.get("name")
    names["sale_deed"] = deed.get("owner")
    names["valuation_report"] = val.get("owner")
    if any(names.values()):
        checks.append(cc.check_names(names, form.applicant_name if form else name, name_threshold))
    checks.append(cc.check_dob({"pan": pan.get("dob"), "aadhaar": aad.get("dob"),
                                "application_form": form.dob if form else None}))
    pans: dict[str, str | None] = {"pan_card": pan.get("_pan_full"), "form16": f16.get("_pan_full")}
    for p in itrs:
        pans[f"itr_{p.get('ay')}"] = p.get("_pan_full")
    for _r, s in by_type.get(DocType.SALARY_SLIP, []):
        pans.setdefault("salary_slip", s.get("_pan_full"))
    checks.append(cc.check_pan(pans))
    checks.append(cc.check_address("aadhaar", aad.get("address"), "bank_statement", stmt.get("address")))
    slip_list = [s for _r, s in by_type.get(DocType.SALARY_SLIP, [])]
    employers: dict[str, str | None] = {
        "salary_slip": next((s.get("employer") for s in slip_list if s.get("employer")), None),
        "form16": f16.get("employer"),
        "bank_salary_credit": cc.salary_narration_employer(bundle.transactions),
        "application_form": form.employer_or_business if form and form.employment_type == EmploymentType.SALARIED else None,
    }
    if slip_list or f16:
        checks.append(cc.check_employer(employers))
    checks.append(cc.check_salary_vs_credit(bundle.salary_slips, bundle.transactions))
    checks.append(cc.check_form16_vs_slips(f16.get("gross_salary"), bundle.salary_slips))
    checks.append(cc.check_property_address(deed.get("property_address"), val.get("property_address")))
    for check, flags in checks:
        if check is not None:
            check.values = {k: _jsonable(v) for k, v in check.values.items()}
            bundle.cross_checks.append(check)
        bundle.flags.extend(flags)
