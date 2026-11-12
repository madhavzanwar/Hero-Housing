"""Document tampering / forgery heuristics. Each returns Flags with evidence (never raw PII)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.schemas import DocType, Flag, Severity, Transaction

_DEFAULT_SUSPICIOUS = ["photoshop", "gimp", "canva", "ilovepdf", "smallpdf", "pdf editor", "sejda",
                       "foxit phantompdf"]
TAMPER_CODES = {"DOC_PRODUCER_SUSPICIOUS", "DOC_FONT_ANOMALY", "DOC_MODIFIED_AFTER_CREATION",
                "DOC_ARITHMETIC_MISMATCH"}


def metadata_flags(doc_id: str, doc_type: DocType, meta: dict[str, Any],
                   suspicious: list[str] | None = None) -> list[Flag]:
    flags: list[Flag] = []
    tools = [s.lower() for s in (suspicious or _DEFAULT_SUSPICIOUS)]
    for key in ("producer", "creator"):
        val = str(meta.get(key) or "")
        hit = next((t for t in tools if t in val.lower()), None)
        if hit:
            flags.append(Flag(
                code="DOC_PRODUCER_SUSPICIOUS", severity=Severity.HIGH, document_id=doc_id,
                title="Document saved by an editing tool",
                detail=f"{doc_type.value} PDF {key} is '{val}' - an online PDF/image editor, not the issuer's "
                       "system. Originals from payroll/bank systems are not re-saved by editors.",
                evidence={"field": key, "value": val, "matched": hit}))
            break
    cd, md = meta.get("creation_date"), meta.get("mod_date")
    if cd and md:
        try:
            c, m = datetime.fromisoformat(cd), datetime.fromisoformat(md)
            if m - c > timedelta(minutes=5):
                flags.append(Flag(
                    code="DOC_MODIFIED_AFTER_CREATION", severity=Severity.MEDIUM, document_id=doc_id,
                    title="PDF modified after it was issued",
                    detail=f"{doc_type.value} was created {c.date().isoformat()} but modified {m.date().isoformat()} "
                           f"({(m - c).days} days later).",
                    evidence={"creation_date": cd, "mod_date": md, "days": (m - c).days}))
        except ValueError:
            pass
    return flags


def font_flags(doc_id: str, doc_type: DocType, amount_fonts: list[tuple[str, str]],
               font_runs: dict[str, int] | None = None) -> list[Flag]:
    """Issuer systems print every figure in one typeface; an edited figure often uses another."""
    if doc_type not in (DocType.SALARY_SLIP, DocType.FORM16, DocType.ITR, DocType.BANK_STATEMENT) or not amount_fonts:
        return []
    by_font: dict[str, list[str]] = {}
    for tok, fam in amount_fonts:
        by_font.setdefault(fam, []).append(tok)
    if len(by_font) < 2:
        return []
    # the document's house font = the family used by most text runs (labels + figures)
    runs = font_runs or {f: len(t) for f, t in by_font.items()}
    main = max(by_font, key=lambda f: (runs.get(f, 0), len(by_font[f])))
    odd = {f: toks for f, toks in by_font.items() if f != main}
    odd_tokens = [t for toks in odd.values() for t in toks]
    return [Flag(
        code="DOC_FONT_ANOMALY", severity=Severity.HIGH, document_id=doc_id,
        title="Figures typed in a different font",
        detail=f"{len(odd_tokens)} amount(s) on the {doc_type.value} use font '{', '.join(odd)}' while the rest use "
               f"'{main}' - typical of figures overwritten after issue.",
        evidence={"main_font": main, "odd_fonts": sorted(odd), "odd_amounts": odd_tokens[:8]})]


def slip_flags(doc_id: str, fields: dict[str, Any]) -> list[Flag]:
    flags: list[Flag] = []
    gross, ded, net = fields.get("gross"), fields.get("total_deductions"), fields.get("net_pay")
    if gross and ded is not None and net and abs(gross - ded - net) > 1.0:
        flags.append(Flag(
            code="DOC_ARITHMETIC_MISMATCH", severity=Severity.HIGH, document_id=doc_id,
            title="Salary slip does not add up",
            detail=f"Gross {gross:,.0f} - deductions {ded:,.0f} = {gross - ded:,.0f}, but net pay shown is {net:,.0f}.",
            evidence={"gross": gross, "total_deductions": ded, "net_pay": net, "difference": round(gross - ded - net, 2)}))
    amounts = [a for a in fields.get("_amounts", []) if a and a >= 100]
    if len(amounts) >= 4:
        rnd = [a for a in amounts if a % 1000 == 0]
        share = len(rnd) / len(amounts)
        if share >= 0.6:
            flags.append(Flag(
                code="DOC_ROUND_NUMBERS", severity=Severity.MEDIUM, document_id=doc_id,
                title="Unnaturally round salary figures",
                detail=f"{len(rnd)} of {len(amounts)} amounts on the slip are exact thousands; payroll output "
                       "(PF at 12%, tax, pro-rata) rarely is.",
                evidence={"round_share": round(share, 2), "round_amounts": rnd[:8]}))
    return flags


def statement_round_flag(doc_id: str, txns: list[Transaction], threshold: float) -> list[Flag]:
    if len(txns) < 20:
        return []
    rnd = sum(1 for t in txns if abs(t.amount) >= 1000 and abs(t.amount) % 1000 == 0)
    share = rnd / len(txns)
    if share <= threshold:
        return []
    return [Flag(code="DOC_ROUND_NUMBERS", severity=Severity.MEDIUM, document_id=doc_id,
                 title="Statement dominated by round-thousand amounts",
                 detail=f"{share:.0%} of {len(txns)} transactions are exact thousands (policy threshold {threshold:.0%}).",
                 evidence={"round_share": round(share, 3), "threshold": threshold, "transactions": len(txns)})]


def duplicate_flags(docs: list[tuple[str, str, DocType, str]],
                    statements: dict[str, list[Transaction]]) -> list[Flag]:
    """docs: (doc_id, filename, doc_type, sha256)."""
    flags: list[Flag] = []
    seen: dict[str, str] = {}
    for doc_id, fname, _dt, sha in docs:
        if sha in seen:
            flags.append(Flag(code="DOC_DUPLICATE", severity=Severity.MEDIUM, document_id=doc_id,
                              title="Same file uploaded twice",
                              detail=f"'{fname}' is byte-identical to document {seen[sha]}.",
                              evidence={"sha256": sha[:16], "duplicate_of": seen[sha]}))
        else:
            seen[sha] = doc_id
    ids = list(statements)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            sa = [(t.date, t.amount) for t in statements[a]]
            sb = [(t.date, t.amount) for t in statements[b]]
            if len(sa) >= 10 and len(sb) >= 10:
                common = len(set(sa) & set(sb))
                if common / min(len(sa), len(sb)) > 0.9:
                    flags.append(Flag(code="DOC_DUPLICATE", severity=Severity.HIGH, document_id=b,
                                      title="Duplicate bank statement",
                                      detail=f"Statement {b} repeats {common} transactions of statement {a}.",
                                      evidence={"overlap": common, "of": a}))
    return flags


def composite_flag(doc_id: str, doc_type: DocType, flags: list[Flag]) -> list[Flag]:
    """Two or more independent tamper signals on one document -> CRITICAL forgery flag."""
    codes = sorted({f.code for f in flags if f.document_id == doc_id and f.code in TAMPER_CODES})
    if len(codes) < 2:
        return []
    return [Flag(code="DOC_TAMPERED", severity=Severity.CRITICAL, document_id=doc_id,
                 title=f"{doc_type.value.replace('_', ' ').title()} appears forged",
                 detail=f"Independent tamper signals on the same document: {', '.join(codes)}.",
                 evidence={"signals": codes})]
