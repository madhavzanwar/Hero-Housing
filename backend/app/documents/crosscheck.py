"""Cross-document consistency checks (name, DOB, PAN, address, employer, salary vs bank credit,
Form 16 vs slips, property address)."""
from __future__ import annotations

import re
from datetime import date
from statistics import mean
from typing import Any

from app.documents._mask import mask_pan
from app.schemas import CrossCheck, Flag, Severity, Transaction

try:
    from rapidfuzz import fuzz as _fuzz

    def _ratio(a: str, b: str) -> float:
        return _fuzz.ratio(a, b) / 100.0

    def _token_set(a: str, b: str) -> float:
        return _fuzz.token_set_ratio(a, b) / 100.0

    def _partial(a: str, b: str) -> float:
        return _fuzz.partial_ratio(a, b) / 100.0
except ImportError:  # pragma: no cover - difflib fallback
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _token_set(a: str, b: str) -> float:
        ta, tb = set(a.split()), set(b.split())
        inter = " ".join(sorted(ta & tb))
        ra = " ".join(sorted(ta - tb))
        rb = " ".join(sorted(tb - ta))
        cands = [_ratio(inter, f"{inter} {ra}".strip()), _ratio(inter, f"{inter} {rb}".strip()),
                 _ratio(f"{inter} {ra}".strip(), f"{inter} {rb}".strip())]
        return max(cands) if inter else _ratio(" ".join(sorted(ta)), " ".join(sorted(tb)))

    def _partial(a: str, b: str) -> float:
        short, long_ = sorted((a, b), key=len)
        if not short:
            return 0.0
        return max(_ratio(short, long_[i:i + len(short)]) for i in range(max(len(long_) - len(short), 0) + 1))

_TITLES = r"\b(MR|MRS|MS|MISS|DR|SHRI|SMT|KUM|M/S|SRI)\b\.?"
_ORG_NOISE = r"\b(PVT|PRIVATE|LTD|LIMITED|LLP|INDIA|CO|COMPANY|THE|AND|OF|GOVT|AIDED|INC|CORP)\b"


def norm_name(s: str) -> str:
    s = re.sub(_TITLES, " ", s.upper())
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def name_similarity(a: str | None, b: str | None) -> float:
    """Order/middle-name tolerant; also handles OCR-glued names ('AARAVSUNILDESHMUKH')."""
    if not a or not b:
        return 0.0
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    score = _token_set(na, nb)
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    for short, long_ in ((na, cb), (nb, ca)):
        toks = [t for t in short.split() if len(t) > 1]
        if toks and all(t in long_ for t in toks):
            score = max(score, 0.97)
    if len(na.split()) == 1 or len(nb.split()) == 1:
        score = max(score, _ratio(ca, cb))
    return round(score, 3)


def resegment(name: str | None, vocab: set[str]) -> str | None:
    """Re-insert spaces into an OCR-glued upper-case name using words seen elsewhere."""
    if not name or " " in name.strip():
        return name
    s = re.sub(r"[^A-Za-z]", "", name).upper()
    words = sorted({w for w in vocab if len(w) > 1}, key=len, reverse=True)
    best: dict[int, list[str] | None] = {0: []}
    for i in range(1, len(s) + 1):
        best[i] = None
        for w in words:
            j = i - len(w)
            if j >= 0 and best.get(j) is not None and s[j:i] == w:
                best[i] = best[j] + [w]  # type: ignore[operator]
                break
    seg = best.get(len(s))
    if not seg:
        return name
    out = " ".join(seg)
    return out.title() if name[:1].isupper() and not name.isupper() else out


def norm_org(s: str) -> str:
    s = re.sub(r"[^A-Z ]", " ", s.upper())
    return re.sub(r"\s+", " ", re.sub(_ORG_NOISE, " ", s)).strip()


def org_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    na, nb = norm_org(a), norm_org(b)
    if not na or not nb:
        return 0.0
    score = max(_token_set(na, nb), _partial(na.replace(" ", ""), nb.replace(" ", "")))
    for x, y in ((na, nb), (nb, na)):  # acronym: 'VSPM NAGPUR' vs 'Vidarbha Shikshan Prasarak Mandal'
        initials = "".join(w[0] for w in x.split())
        if len(initials) >= 3 and initials in y.split():
            score = max(score, 0.9)
    first_a, first_b = na.split()[0], nb.split()[0]
    if len(first_a) >= 4 and first_a == first_b:
        score = max(score, 0.9)
    return round(score, 3)


def _flag(code: str, title: str, detail: str, sev: Severity, **ev: Any) -> Flag:
    return Flag(code=code, title=title, detail=detail, severity=sev, evidence=ev)


def check_names(names: dict[str, str | None], reference: str | None, threshold: float
                ) -> tuple[CrossCheck, list[Flag]]:
    vals = {k: v for k, v in names.items() if v}
    ref = reference or next(iter(vals.values()), None)
    scores = {k: name_similarity(v, ref) for k, v in vals.items()}
    worst = min(scores.values()) if scores else 1.0
    bad = {k: s for k, s in scores.items() if s < threshold}
    cc = CrossCheck(field="name", values={**vals, "application_form": reference}, match=not bad, score=worst,
                    note="All documents carry the applicant's name" if not bad else
                    f"Name differs on: {', '.join(bad)}")
    flags = []
    if bad:
        sev = Severity.HIGH if min(bad.values()) < 0.6 else Severity.MEDIUM
        flags.append(_flag("NAME_MISMATCH", "Applicant name does not match across documents",
                           f"Name on {', '.join(bad)} differs from '{ref}' (lowest similarity {min(bad.values()):.2f}, "
                           f"threshold {threshold:.2f}).", sev, scores=scores, threshold=threshold))
    return cc, flags


def check_dob(dobs: dict[str, date | None]) -> tuple[CrossCheck | None, list[Flag]]:
    vals = {k: v for k, v in dobs.items() if v}
    if len(vals) < 2:
        return None, []
    distinct = set(vals.values())
    ok = len(distinct) == 1
    cc = CrossCheck(field="dob", values={k: v.isoformat() for k, v in vals.items()}, match=ok,
                    score=1.0 if ok else 0.0, note="Date of birth consistent" if ok else "Dates of birth differ")
    flags = [] if ok else [_flag("DOB_MISMATCH", "Date of birth mismatch",
                                 "Date of birth differs between " + ", ".join(f"{k}={v.isoformat()}" for k, v in vals.items()),
                                 Severity.HIGH, values={k: v.isoformat() for k, v in vals.items()})]
    return cc, flags


def check_pan(pans: dict[str, str | None]) -> tuple[CrossCheck | None, list[Flag]]:
    """Compares full PANs transiently; only masked values leave this function."""
    vals = {k: v for k, v in pans.items() if v}
    if len(vals) < 2:
        return None, []
    ok = len(set(vals.values())) == 1
    masked = {k: mask_pan(v) for k, v in vals.items()}
    cc = CrossCheck(field="pan", values=masked, match=ok, score=1.0 if ok else 0.0,
                    note="Same PAN on all documents" if ok else "Different PANs across documents")
    flags = [] if ok else [_flag("PAN_MISMATCH", "PAN differs across documents",
                                 "PAN on " + ", ".join(f"{k} ({v})" for k, v in masked.items()) + " do not agree.",
                                 Severity.HIGH, values=masked)]
    return cc, flags


def check_address(a_label: str, a: str | None, b_label: str, b: str | None
                  ) -> tuple[CrossCheck | None, list[Flag]]:
    if not a or not b:
        return None, []
    pin_a, pin_b = re.findall(r"\b\d{6}\b", a), re.findall(r"\b\d{6}\b", b)
    squash = re.compile(r"[^A-Z0-9]")
    score = max(_token_set(a.upper(), b.upper()), _partial(squash.sub("", a.upper()), squash.sub("", b.upper())))
    ok = (bool(pin_a) and bool(pin_b) and pin_a[-1] == pin_b[-1]) or score >= 0.75
    cc = CrossCheck(field="address", values={a_label: a, b_label: b}, match=ok, score=round(score, 3),
                    note="Address consistent" if ok else "Address differs (pincode/locality)")
    flags = [] if ok else [_flag("ADDRESS_MISMATCH", "Address mismatch",
                                 f"Address on {a_label} and {b_label} differ (similarity {score:.2f}).",
                                 Severity.LOW, similarity=round(score, 3))]
    return cc, flags


def salary_narration_employer(txns: list[Transaction]) -> str | None:
    for t in txns:
        if t.category == "SALARY":
            d = re.sub(r"^(NEFT|RTGS|IMPS)\s*CR\W*[A-Z]{4}0[A-Z0-9]{6}\W*", "", t.description.upper())
            d = re.split(r"\bSALARY\b|\bSAL\b", d)[0]
            return d.strip(" -/") or None
    return None


def check_employer(sources: dict[str, str | None]) -> tuple[CrossCheck | None, list[Flag]]:
    vals = {k: v for k, v in sources.items() if v}
    if len(vals) < 2:
        return None, []
    ref_key = next((k for k in ("salary_slip", "form16", "application_form") if k in vals), next(iter(vals)))
    ref = vals[ref_key]
    scores = {k: org_similarity(v, ref) for k, v in vals.items() if k != ref_key}
    bad = {k: s for k, s in scores.items() if s < 0.75}
    cc = CrossCheck(field="employer", values=vals, match=not bad, score=min(scores.values()) if scores else 1.0,
                    note="Employer consistent across slips, Form 16 and salary credits" if not bad else
                    f"Employer differs on: {', '.join(bad)}")
    flags = [] if not bad else [_flag("EMPLOYER_MISMATCH", "Employer mismatch",
                                      f"Employer on {', '.join(bad)} does not match '{ref}'.", Severity.MEDIUM,
                                      scores=scores)]
    return cc, flags


def check_salary_vs_credit(slips: list[dict[str, Any]], txns: list[Transaction], tolerance: float = 0.05
                           ) -> tuple[CrossCheck | None, list[Flag]]:
    nets = [s["net"] for s in slips if s.get("net")]
    credits = [t for t in txns if t.category == "SALARY" and t.amount > 0]
    if not nets or not credits:
        return None, []
    months = {s.get("month") for s in slips if s.get("month")}
    in_months = [t.amount for t in credits if t.date.strftime("%Y-%m") in months] or [t.amount for t in credits]
    slip_avg, credit_avg = mean(nets), mean(in_months)
    diff = (slip_avg - credit_avg) / slip_avg if slip_avg else 0.0
    ok = abs(diff) <= tolerance
    cc = CrossCheck(field="salary_vs_credit", values={"salary_slip_net_avg": round(slip_avg, 2),
                                                      "bank_salary_credit_avg": round(credit_avg, 2)},
                    match=ok, score=round(max(0.0, 1 - abs(diff)), 3),
                    note=f"Slip net vs bank salary credit differ by {diff:+.1%} (tolerance ±{tolerance:.0%})")
    flags = []
    if not ok:
        sev = Severity.HIGH if abs(diff) > 0.15 else Severity.MEDIUM
        flags.append(_flag("SALARY_CREDIT_MISMATCH", "Salary slip net pay not seen in bank",
                           f"Average net pay on slips Rs {slip_avg:,.0f} vs average salary credit Rs {credit_avg:,.0f} "
                           f"({diff:+.0%}).", sev, slip_net_avg=round(slip_avg, 2), credit_avg=round(credit_avg, 2),
                           difference_pct=round(diff, 4), tolerance=tolerance))
    return cc, flags


def check_form16_vs_slips(form16_gross: float | None, slips: list[dict[str, Any]]
                          ) -> tuple[CrossCheck | None, list[Flag]]:
    gross = [s["gross"] for s in slips if s.get("gross")]
    if not form16_gross or not gross:
        return None, []
    annual = mean(gross) * 12
    diff = (annual - form16_gross) / form16_gross
    ok = abs(diff) <= 0.30  # increments / bonus between FY and current slips
    cc = CrossCheck(field="form16_vs_slips", values={"form16_gross_salary": form16_gross,
                                                     "slips_annualised_gross": round(annual, 2)},
                    match=ok, score=round(max(0.0, 1 - abs(diff)), 3),
                    note=f"Annualised slip gross vs Form 16 gross: {diff:+.0%}")
    flags = [] if ok else [_flag("FORM16_SLIP_MISMATCH", "Salary slips inconsistent with Form 16",
                                 f"Slips annualise to Rs {annual:,.0f} but Form 16 shows Rs {form16_gross:,.0f} "
                                 f"({diff:+.0%}).", Severity.HIGH if abs(diff) > 0.5 else Severity.MEDIUM,
                                 form16_gross=form16_gross, slips_annualised=round(annual, 2),
                                 difference_pct=round(diff, 4))]
    return cc, flags


def check_property_address(deed: str | None, valuation: str | None) -> tuple[CrossCheck | None, list[Flag]]:
    if not deed or not valuation:
        return None, []
    squash = re.compile(r"[^A-Z0-9]")
    score = max(_token_set(deed.upper(), valuation.upper()),
                _ratio(squash.sub("", deed.upper()), squash.sub("", valuation.upper())))
    ok = score >= 0.7
    cc = CrossCheck(field="property_address", values={"sale_deed": deed, "valuation_report": valuation},
                    match=ok, score=round(score, 3),
                    note="Valuation is for the property in the deed" if ok else "Deed and valuation addresses differ")
    flags = [] if ok else [_flag("PROPERTY_ADDRESS_MISMATCH", "Valuation may be for a different property",
                                 f"Deed and valuation report addresses differ (similarity {score:.2f}).",
                                 Severity.MEDIUM, similarity=round(score, 3))]
    return cc, flags
