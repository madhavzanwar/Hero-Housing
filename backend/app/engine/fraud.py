"""Fraud & AML checks: negative-list / PEP / sanctions screening (synthetic list), document
tampering flags from the document layer, income inflation, round-number and duplicate-statement
heuristics, cash-deposit spikes (PMLA) and high-risk merchants.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.engine.eligibility import income_evidence
from app.engine.finance import fmt_inr, pct
from app.engine.masking import mask_pan, redact_text
from app.engine.rules import hit
from app.policy.loader import Policy
from app.schemas import (
    ApplicationForm,
    BankAnalytics,
    DocType,
    DocumentBundle,
    Flag,
    Product,
    RuleCategory,
    RuleHit,
    RuleOutcome,
    Severity,
)

OC = RuleOutcome
S = Severity
_SELF_COMPUTED = ("INCOME_INFLATION", "ROUND", "DUP")
_FRAUD_HINTS = ("TAMPER", "FONT", "PRODUCER", "METADATA", "EDIT", "FORG", "MODIF", "SIGNATURE", "PHOTOSHOP")


def normalize_name(name: str) -> str:
    words = re.sub(r"[^a-z ]", " ", name.lower()).split()
    words = [w for w in words if w not in {"mr", "mrs", "ms", "dr", "shri", "smt", "kumari"}]
    return " ".join(sorted(words))


def name_similarity(a: str, b: str) -> float:
    """Token-sorted similarity in [0, 1] (order-insensitive, honorific-insensitive)."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def screen_name(name: str, pan_masked: str | None, policy: Policy) -> list[dict[str, Any]]:
    thr = float(policy.get("fraud.name_match_threshold", 0.85))
    out = []
    for e in policy.negative_list():
        score = name_similarity(name, str(e.get("name", "")))
        if score >= thr:
            pan_match: bool | None = None
            if pan_masked and e.get("pan_masked"):
                pan_match = mask_pan(pan_masked)[-5:] == str(e["pan_masked"])[-5:]
            out.append({**e, "score": round(score, 3), "pan_match": pan_match})
    return out


def _negative_list_hits(form: ApplicationForm, bundle: DocumentBundle, policy: Policy) -> list[RuleHit]:
    hits: list[RuleHit] = []
    people = [(form.applicant_name, bundle.identity.get("pan_masked"), "Applicant")]
    if form.co_applicant:
        people.append((form.co_applicant.name, None, "Co-applicant"))
    any_match = False
    for name, pan, role in people:
        for m in screen_name(name, pan, policy):
            any_match = True
            typ = str(m.get("type", "")).upper()
            confirmed = m["pan_match"] is True or m["score"] >= 0.97
            ev = {"screened_name": name, "list_name": m["name"], "list_type": typ, "match_score": m["score"],
                  "pan_match": m["pan_match"], "list_detail": m.get("detail", ""), "role": role}
            if m["pan_match"] is False:
                confirmed = False
            if typ == "PEP":
                hits.append(hit(policy, "FRD-NEG-01", OC.WARN,
                                f"{role} {name} matches a politically exposed person entry ({pct(m['score'], 0)} name match); "
                                f"enhanced due diligence and senior management approval are required.",
                                effect="REFER", severity=S.HIGH, evidence=ev))
            elif typ == "SANCTIONS":
                hits.append(hit(policy, "FRD-NEG-01", OC.FAIL,
                                f"{role} {name} matches a sanctions-list designation ({pct(m['score'], 0)} name match)"
                                + ("; relationship cannot be opened." if confirmed else "; match must be cleared by compliance."),
                                effect="DECLINE" if confirmed else "REFER", severity=S.CRITICAL, evidence=ev))
            else:
                label = "internal defaulter list" if typ == "INTERNAL_DEFAULTER" else "industry fraud database"
                hits.append(hit(policy, "FRD-NEG-01", OC.FAIL if confirmed else OC.WARN,
                                f"{role} {name} matches the {label} ({pct(m['score'], 0)} name match"
                                + (", PAN matches" if m["pan_match"] else "") + ").",
                                effect="DECLINE" if confirmed else "REFER", severity=S.CRITICAL if confirmed else S.HIGH,
                                evidence=ev))
    if not any_match:
        hits.append(hit(policy, "FRD-NEG-01", OC.PASS,
                        f"No match on PEP, sanctions, internal-defaulter or fraud lists "
                        f"({len(policy.negative_list())} entries screened)."))
    return hits


def _flag_hits(bundle: DocumentBundle, policy: Policy) -> list[RuleHit]:
    seen: set[tuple[str, str | None]] = set()
    flags: list[Flag] = list(bundle.flags)
    for d in bundle.documents:
        for f in d.flags:
            flags.append(f if f.document_id else f.model_copy(update={"document_id": d.id}))
    hits: list[RuleHit] = []
    for f in flags:
        key = (f.code, f.document_id)
        if key in seen or any(s in f.code.upper() for s in _SELF_COMPUTED):
            continue
        seen.add(key)
        fraudish = any(h in f.code.upper() for h in _FRAUD_HINTS) or f.code.upper().startswith("DOC_")
        cat = RuleCategory.FRAUD if fraudish else RuleCategory.DOCUMENT
        if f.severity == S.CRITICAL:
            outcome, effect = OC.FAIL, "DECLINE"
        elif f.severity == S.HIGH:
            outcome, effect = OC.FAIL, "REFER"
        elif f.severity == S.MEDIUM:
            outcome, effect = OC.WARN, "CONDITION"
        else:
            outcome, effect = OC.INFO, "NONE"
        ev: dict[str, Any] = {"flag_code": f.code, "document_id": f.document_id, **f.evidence}
        if effect == "CONDITION":
            ev["condition"] = "SUBMIT_DOC"
        hits.append(hit(policy, "FRD-DOC-01", outcome, f"{f.title}: {redact_text(f.detail)}", effect=effect,
                        severity=f.severity, evidence=ev, category=cat))
    # independent producer / creator metadata check
    producers = [p.lower() for p in policy.get("fraud.suspicious_pdf_producers", [])]
    flagged_docs = {f.document_id for f in flags if "PRODUCER" in f.code.upper() or "METADATA" in f.code.upper()}
    for d in bundle.documents:
        keys = ("producer", "creator", "Producer", "Creator", "/Producer", "/Creator")
        meta = " ".join(str(d.metadata.get(k, "")) for k in keys)
        tool = next((p for p in producers if p in meta.lower()), None)
        if tool and d.id not in flagged_docs:
            hits.append(hit(policy, "FRD-DOC-02", OC.FAIL,
                            f"{d.doc_type.value.replace('_', ' ').title()} '{d.filename}' was last written by '{tool}', "
                            f"an editing tool not used by issuers; original document required.",
                            effect="REFER", severity=S.HIGH, evidence={"document_id": d.id, "producer": meta.strip()}))
    return hits


def _income_inflation(form: ApplicationForm, bundle: DocumentBundle, bank: BankAnalytics, policy: Policy) -> list[RuleHit]:
    tol = float(policy.get("fraud.income_inflation_tolerance", 0.15))
    dec = float(policy.get("fraud.income_inflation_decline", 0.40))
    inc = income_evidence(form, bundle, bank, policy)
    declared = inc["declared"]
    src = inc["sources"]
    # evidence: bank salary credit (salaried) / ITR (self-employed), and slip vs bank for tampered slips
    comparisons: list[tuple[str, float, float, str]] = []  # (label, claimed, evidenced, evidence_name)
    if "bank_salary_credit" in src:
        comparisons.append(("declared income", declared, src["bank_salary_credit"], "bank salary credit"))
        if "salary_slips_net" in src:
            comparisons.append(
                ("net pay on salary slips", src["salary_slips_net"], src["bank_salary_credit"], "bank salary credit"))
    elif "salary_slips_net" in src:
        comparisons.append(("declared income", declared, src["salary_slips_net"], "salary slips"))
    if "itr_monthly_after_haircut" in src:
        itr_raw = src["itr_monthly_after_haircut"] / (1 - float(policy.get("eligibility.self_employed_income_haircut", 0.1)))
        comparisons.append(("declared income", declared, itr_raw, "ITR income"))
    if not comparisons:
        return [hit(policy, "FRD-INC-01", OC.INFO, "No independent income evidence available to test declared income.",
                    severity=S.LOW)]
    worst = max(comparisons, key=lambda c: (c[1] - c[2]) / c[1] if c[1] else 0)
    label, claimed, evidenced, ev_name = worst
    gap = (claimed - evidenced) / claimed if claimed else 0.0
    ev = {"claimed": round(claimed, 2), "evidenced": round(evidenced, 2), "gap": round(gap, 4), "basis": label,
          "evidence_source": ev_name, "tolerance": tol, "decline_at": dec}
    if gap > dec:
        return [hit(policy, "FRD-INC-01", OC.FAIL,
                    f"The {label} of {fmt_inr(claimed)} a month is {pct(gap, 0)} higher than the {ev_name} of "
                    f"{fmt_inr(evidenced)}; this is treated as income misrepresentation.",
                    effect="DECLINE", severity=S.CRITICAL, evidence=ev)]
    if gap > tol:
        return [hit(policy, "FRD-INC-01", OC.WARN,
                    f"The {label} of {fmt_inr(claimed)} is {pct(gap, 0)} above the {ev_name} of {fmt_inr(evidenced)}; "
                    f"the lower figure is used and the difference must be explained.",
                    effect="REFER", severity=S.HIGH, evidence=ev)]
    return [hit(policy, "FRD-INC-01", OC.PASS,
                f"Declared income is consistent with the {ev_name} (difference {pct(max(gap, 0.0), 0)}).", evidence=ev)]


def _statement_hits(form: ApplicationForm, bundle: DocumentBundle, bank: BankAnalytics, policy: Policy) -> list[RuleHit]:
    hits: list[RuleHit] = []
    bcfg = policy.section("banking")
    n_txn = sum(int(m.get("txn_count", 0)) for m in bank.monthly)
    # round numbers
    rshare = float(policy.get("fraud.round_number_share", 0.6))
    if n_txn >= 10:
        if bank.round_number_share > rshare:
            hits.append(hit(policy, "FRD-RND-01", OC.WARN,
                            f"{pct(bank.round_number_share, 0)} of statement transactions are exact multiples of ₹1,000 "
                            f"(threshold {pct(rshare, 0)}), a pattern typical of fabricated statements.",
                            effect="REFER", severity=S.HIGH, evidence={"share": bank.round_number_share}))
        else:
            hits.append(hit(policy, "FRD-RND-01", OC.PASS,
                            f"Round-number transactions are {pct(bank.round_number_share, 0)} of the statement.",
                            evidence={"share": bank.round_number_share}))
    # duplicates: identical files, docs-layer flags, or repeated transaction blocks
    stmts = [d for d in bundle.documents if d.doc_type == DocType.BANK_STATEMENT]
    shas = [d.sha256 for d in stmts if d.sha256]
    dup_files = len(shas) - len(set(shas))
    dup_flags = [f for f in bundle.flags if "DUP" in f.code.upper()]
    for d in bundle.documents:
        dup_flags += [f for f in d.flags if "DUP" in f.code.upper()]
    if dup_files or dup_flags or bank.duplicate_txn_share > 0.2:
        hits.append(hit(policy, "FRD-DUP-01", OC.FAIL,
                        "The same bank statement (or the same transaction sequence) was submitted more than once"
                        + (f"; {pct(bank.duplicate_txn_share, 0)} of transactions repeat verbatim."
                           if bank.duplicate_txn_share > 0.2 else "."),
                        effect="REFER", severity=S.HIGH,
                        evidence={"duplicate_files": dup_files, "flags": [f.code for f in dup_flags],
                                  "duplicate_txn_share": bank.duplicate_txn_share}))
    # cash
    if bank.cash_deposit_spikes:
        cond = "END_USE_DECLARATION" if form.product == Product.LAP else "SOURCE_OF_FUNDS"
        big = max(bank.cash_deposit_spikes, key=lambda s: s["amount"])
        hits.append(hit(policy, "FRD-CASH-01", OC.WARN,
                        f"{len(bank.cash_deposit_spikes)} large cash deposit(s) found, the largest {fmt_inr(big['amount'])} on "
                        f"{big['date']}; source of funds must be evidenced.",
                        effect="CONDITION", severity=S.MEDIUM,
                        evidence={"spikes": bank.cash_deposit_spikes[:5], "condition": cond}))
    share_ref = float(bcfg.get("cash_deposit_share_refer", 0.30))
    if bank.total_credits > 0:
        if bank.cash_deposit_share > share_ref:
            hits.append(hit(policy, "FRD-CASH-02", OC.WARN,
                            f"Cash deposits are {pct(bank.cash_deposit_share, 0)} of all credits "
                            f"({fmt_inr(bank.cash_deposit_total)}), "
                            f"above the {pct(share_ref, 0)} PMLA monitoring threshold.",
                            effect="REFER", severity=S.HIGH,
                            evidence={"share": bank.cash_deposit_share, "total": bank.cash_deposit_total}))
        else:
            hits.append(hit(policy, "FRD-CASH-02", OC.PASS,
                            f"Cash deposits are {pct(bank.cash_deposit_share, 0)} of credits, "
                            f"within the {pct(share_ref, 0)} threshold.",
                            evidence={"share": bank.cash_deposit_share}))
    # high-risk merchants
    hr_ref = float(bcfg.get("high_risk_share_refer", 0.05))
    if bank.high_risk_merchants:
        total = sum(float(e["amount"]) for e in bank.high_risk_merchants)
        names = ", ".join(str(e["merchant"]) for e in bank.high_risk_merchants[:4])
        over = bank.high_risk_debit_share > hr_ref
        hits.append(hit(policy, "FRD-HRM-01", OC.WARN,
                        f"{fmt_inr(total)} spent on gambling / betting / crypto merchants ({names}), "
                        f"{pct(bank.high_risk_debit_share)} of debits"
                        + (f", above the {pct(hr_ref, 0)} threshold." if over else "."),
                        effect="REFER" if over else "NONE", severity=S.HIGH if over else S.LOW,
                        evidence={"merchants": bank.high_risk_merchants, "share": bank.high_risk_debit_share}))
    elif bank.total_debits > 0:
        hits.append(hit(policy, "FRD-HRM-01", OC.PASS, "No gambling, betting or crypto merchants in the statement."))
    return hits


def run(form: ApplicationForm, bundle: DocumentBundle, bank: BankAnalytics, policy: Policy) -> list[RuleHit]:
    hits: list[RuleHit] = []
    hits += _negative_list_hits(form, bundle, policy)
    hits += _flag_hits(bundle, policy)
    hits += _income_inflation(form, bundle, bank, policy)
    hits += _statement_hits(form, bundle, bank, policy)
    return hits
