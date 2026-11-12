"""Underwriting Copilot Q&A — answers grounded ONLY in the case file and the credit policy.

Pipeline:
1. **Route** the question to one or more intents with keyword rules (deterministic).
2. **Retrieve** facts for each intent from the CaseDetail (rule hits, metrics, documents) and the
   policy YAML; each fact becomes a :class:`~app.schemas.Citation`.
3. **Template** a plain-language answer that cites rule IDs in square brackets.
4. If an LLM is reachable, it may *rephrase* using only those facts. Its draft is rejected (and the
   template used) unless every rule ID it cites exists and every number it states appears in the facts.

Out-of-scope or PII-unmasking questions are refused politely.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from app.agent.llm import LLMProvider, get_provider
from app.schemas import (
    CaseDetail,
    Citation,
    CopilotAnswer,
    DecisionOutcome,
    RuleCategory,
    RuleHit,
    RuleOutcome,
)

log = logging.getLogger(__name__)

RULE_ID_RE = re.compile(r"\b[A-Z]{2,5}(?:-[A-Z0-9]{1,10}){1,3}\b")
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

REFUSAL = ("I can only answer questions about this underwriting case — its documents, rules fired, "
           "eligibility (FOIR, LTV, EMI, max loan), bank analytics, fraud/compliance checks, risk model, "
           "repayment capacity, conditions and the credit policy. Try e.g. \"Why was this case referred?\", "
           "\"What is the FOIR?\" or \"What if the loan is ₹30 lakh over 25 years?\".")
PII_REFUSAL = ("I can't reveal unmasked PAN or Aadhaar numbers — only masked identifiers are stored "
               "(DPDP Act 2023; Aadhaar Act s.29). The masked values are shown on the applicant panel.")

_OUT_OF_SCOPE = re.compile(
    r"\b(weather|joke|poem|song|recipe|movie|cricket|football|stock tip|which stocks?|share price|"
    r"bitcoin price|horoscope|write (?:me )?(?:a |an )?(?:code|program|script|essay|story)|translate|"
    r"ignore (?:all |the |your |previous )*instructions|system prompt|jailbreak|"
    r"other (?:applicants?|customers?|cases?)|another (?:applicant|customer))\b", re.I)
_PII = re.compile(r"\b(unmask|full|complete|entire|actual|real|original)\b.{0,20}\b(pan|aadhaa?r)\b"
                  r"|\b(pan|aadhaa?r)\b.{0,20}\b(unmasked|in full|full number)\b", re.I)

INTENT_PATTERNS: list[tuple[str, str]] = [
    ("what_if", r"what\s*-?\s*if|\bif (?:we|the|i|he|she|they|you|loan|amount|tenure)\b|suppose|instead of|"
                r"\b(?:reduce|lower|cut|increase|extend|change)\b.{0,25}\b(?:loan|amount|tenure|term)\b|scenario"),
    ("decision", r"why|declin|reject|refer|approv|decision|outcome|verdict|summar|overall|status|recommend"),
    ("foir", r"\bfoir\b|obligation|debt.to.income|\bdti\b"),
    ("ltv", r"\bltv\b|loan.to.value|property value|valuation|collateral"),
    ("max_eligible", r"\bmax(?:imum)?\b.{0,20}(?:loan|amount|eligib)|eligib|how much (?:can|could|is)|afford"),
    ("emi", r"\bemis?\b|instal?ments?|monthly payment"),
    ("conditions", r"condition|what (?:is|are) (?:needed|required)|requirement|to get approved|disburs"),
    ("fraud", r"fraud|tamper|forg|fake|manipulat|suspicious|flag|\bpep\b|negative list|sanctions? (?:list|screen|match)|"
              r"\baml\b|launder|red.?flag|inflat|misrepresent|compliance|cersai|end.?use"),
    ("missing_docs", r"missing|pending doc|documents?|upload|\bkyc\b|verified"),
    ("income", r"income|salary|earn|net pay|\bitr\b|form ?16|co.?applicant"),
    ("bank", r"bounce|bank|balance|cash deposit|statement|gambl|betting|merchant|\bnach\b|cheque"),
    ("risk", r"risk|shap|driver|\bpd\b|probability of default|score|grade|model|feature|bureau|cibil"),
    ("capacity", r"capacity|monte.?carlo|forecast|shortfall|stress|health score|surplus|buffer|cash.?flow"),
    ("rate", r"interest|\brate\b|\broi\b|pricing|\bapr\b|spread"),
    ("policy", r"policy|regulat|\brbi\b|guideline|circular|threshold|\bcap\b|limit"),
]
_SPECIFIC_DECISION = re.compile(r"declin|reject|refer|approv|decision|outcome|verdict|summar|overall|status|recommend", re.I)


# --------------------------------------------------------------------------- formatting helpers
def inr(x: float | None) -> str:
    if x is None:
        return "n/a"
    v = float(x)
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:.2f} lakh"
    return f"₹{v:,.0f}"


def pct(x: float | None, nd: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def _policy() -> Any:
    from app.policy.loader import get_policy
    return get_policy()


def _policy_raw() -> dict[str, Any]:
    from app.reports.memo import policy_raw
    return policy_raw()


def policy_rule_index(raw: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Every ``{id: ...}`` entry in the policy YAML, with its dotted path."""
    raw = raw if raw is not None else _policy_raw()
    out: dict[str, dict[str, Any]] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            rid = node.get("id")
            if isinstance(rid, str) and RULE_ID_RE.fullmatch(rid):
                out[rid] = {"path": path, **node}
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    walk(raw, "")
    rules = raw.get("rules")
    if isinstance(rules, dict):  # optional rule catalogue {RULE-ID: {...}}
        for k, v in rules.items():
            if RULE_ID_RE.fullmatch(str(k)):
                out.setdefault(str(k), {"path": f"rules.{k}", **(v if isinstance(v, dict) else {"text": v})})
    return out


def known_rule_ids(case: CaseDetail) -> set[str]:
    ids = {h.rule_id for h in case.decision.rules_fired}
    ids |= {case.eligibility.ltv_rule_id} if case.eligibility.ltv_rule_id else set()
    return ids | set(policy_rule_index())


class _Ctx:
    """Accumulates answer paragraphs and citations for one question."""

    def __init__(self, case: CaseDetail) -> None:
        self.case = case
        self.paras: list[str] = []
        self.cites: list[Citation] = []
        self._seen: set[tuple[str, str]] = set()

    def cite(self, kind: str, ref: str, text: str) -> None:
        if (kind, ref) in self._seen or not ref:
            return
        self._seen.add((kind, ref))
        self.cites.append(Citation(kind=kind, ref=ref, text=text[:300]))  # type: ignore[arg-type]

    def rule(self, h: RuleHit) -> str:
        self.cite("rule", h.rule_id, f"{h.name} — {h.outcome.value}: {h.detail}")
        return f"[{h.rule_id}]"

    def ref(self, rule_id: str) -> str:
        """Cite a rule by ID from this case's hits, else from the policy definition."""
        if not rule_id:
            return ""
        hit = next((h for h in self.case.decision.rules_fired if h.rule_id == rule_id), None)
        if hit:
            return self.rule(hit)
        pr = policy_rule_index().get(rule_id)
        if pr:
            self.cite("rule", rule_id, f"policy {pr['path']}")
        return f"[{rule_id}]"

    def metric(self, name: str, value: str) -> None:
        self.cite("metric", name, value)

    def say(self, text: str) -> None:
        if text:
            self.paras.append(text)


def _hits(case: CaseDetail, pred: Callable[[RuleHit], bool], non_pass: bool = True) -> list[RuleHit]:
    order = {RuleOutcome.FAIL: 0, RuleOutcome.WARN: 1, RuleOutcome.INFO: 2, RuleOutcome.PASS: 3}
    hs = [h for h in case.decision.rules_fired if pred(h) and (not non_pass or h.outcome != RuleOutcome.PASS)]
    return sorted(hs, key=lambda h: (order.get(h.outcome, 9), h.rule_id))


def _has(h: RuleHit, *words: str) -> bool:
    blob = f"{h.rule_id} {h.name}".lower()
    return any(w in blob for w in words)


def _rule_lines(ctx: _Ctx, hits: list[RuleHit], limit: int = 6) -> str:
    return "\n".join(f"- {ctx.rule(h)} {h.name}: {h.detail}" for h in hits[:limit])


# --------------------------------------------------------------------------- intent handlers
def _decision(ctx: _Ctx) -> None:
    c = ctx.case
    d = c.decision
    ctx.metric("decision.outcome", d.outcome.value)
    head = f"Outcome: **{d.outcome.value.replace('_', ' ')}**"
    if d.engine_outcome != d.outcome:
        head += f" (engine said {d.engine_outcome.value}; overridden by {d.decided_by})"
    head += f". The ML model alone suggested {d.model_suggested.value} (PD {pct(c.risk.pd, 2)}, grade {c.risk.grade})."
    if d.outcome in (DecisionOutcome.APPROVE, DecisionOutcome.APPROVE_WITH_CONDITIONS):
        head += f" Sanction {inr(d.sanctioned_amount)} at {pct(d.rate, 2)} for {d.tenure_months} months (EMI {inr(d.emi)})."
    ctx.say(head)
    if d.reasons:
        ctx.say("Key reasons:\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(d.reasons[:5], 1)))
    drivers = _hits(c, lambda h: h.effect in ("DECLINE", "REFER", "REDUCE_AMOUNT", "CONDITION")
                    or h.outcome == RuleOutcome.FAIL)
    if drivers:
        ctx.say("Rules driving the outcome:\n" + _rule_lines(ctx, drivers))
    elif d.outcome == DecisionOutcome.APPROVE:
        ctx.say("No policy rule raised an exception; all checks passed.")
    for o in c.overrides[-1:]:
        ctx.say(f"Override by {o.underwriter}: {o.from_outcome.value} → {o.to_outcome.value}. Reason: {o.reason}")


def _foir(ctx: _Ctx) -> None:
    e = ctx.case.eligibility
    ok = e.foir_actual <= e.foir_cap
    ctx.metric("eligibility.foir_actual", pct(e.foir_actual))
    ctx.metric("eligibility.foir_cap", pct(e.foir_cap, 0))
    ctx.cite("policy", "eligibility.foir_bands", "FOIR cap by monthly assessed income band")
    text = (f"FOIR is **{pct(e.foir_actual)}** against a policy cap of {pct(e.foir_cap, 0)} "
            f"({'within' if ok else 'above'} the cap): existing obligations {inr(e.existing_obligations)} + "
            f"proposed EMI {inr(e.requested_emi)} on assessed income {inr(e.assessed_income)}/month.")
    hits = _hits(ctx.case, lambda h: _has(h, "foir", "obligation"), non_pass=False)
    if hits:
        text += " " + " ".join(ctx.rule(h) for h in hits[:3])
    ctx.say(text)


def _ltv(ctx: _Ctx) -> None:
    c = ctx.case
    e = c.eligibility
    ok = e.ltv_actual <= e.ltv_cap + 1e-9
    ctx.metric("eligibility.ltv_actual", pct(e.ltv_actual))
    ctx.metric("eligibility.ltv_cap", pct(e.ltv_cap, 0))
    ltv_hit = next((h for h in c.decision.rules_fired if h.rule_id == e.ltv_rule_id), None)
    tag = ctx.ref(e.ltv_rule_id)
    text = (f"LTV is **{pct(e.ltv_actual)}** ({inr(e.requested_amount)} on property value "
            f"{inr(c.form.property_value)}) vs cap {pct(e.ltv_cap, 0)} {tag} — "
            f"{'within' if ok else 'above'} the limit. Max loan by LTV: {inr(e.max_loan_by_ltv)}.")
    ref = ltv_hit.reference if ltv_hit and ltv_hit.reference else None
    if ref:
        text += f" Reference: {ref}."
    ctx.say(text)


def _max_eligible(ctx: _Ctx) -> None:
    e = ctx.case.eligibility
    ctx.metric("eligibility.max_eligible_loan", inr(e.max_eligible_loan))
    binding = "FOIR" if e.max_loan_by_foir <= e.max_loan_by_ltv else "LTV"
    text = (f"Maximum eligible loan is **{inr(e.max_eligible_loan)}** (requested {inr(e.requested_amount)}): "
            f"{inr(e.max_loan_by_foir)} by FOIR, {inr(e.max_loan_by_ltv)} by LTV {ctx.ref(e.ltv_rule_id)} — {binding} binds. "
            f"Max affordable EMI {inr(e.max_emi_affordable)} at {pct(e.rate, 2)}, max tenure {e.max_tenure_months} months.")
    if e.tenure_options:
        text += " Tenure options: " + "; ".join(
            f"{t.tenure_months}m → max {inr(t.max_loan)}" for t in e.tenure_options[:4]) + "."
    ctx.say(text)


def _emi(ctx: _Ctx) -> None:
    d, e = ctx.case.decision, ctx.case.eligibility
    ctx.metric("eligibility.requested_emi", inr(e.requested_emi))
    text = (f"EMI on the requested {inr(e.requested_amount)} over {ctx.case.form.tenure_months} months "
            f"at {pct(e.rate, 2)} is **{inr(e.requested_emi)}**")
    if d.emi and abs(d.emi - e.requested_emi) > 1:
        ctx.metric("decision.emi", inr(d.emi))
        text += f"; on the sanctioned {inr(d.sanctioned_amount)} over {d.tenure_months} months it is **{inr(d.emi)}**"
    text += f". Affordable EMI ceiling under FOIR: {inr(e.max_emi_affordable)}."
    ctx.say(text)


def _conditions(ctx: _Ctx) -> None:
    d = ctx.case.decision
    if not d.conditions:
        ctx.say("No conditions are attached to this decision.")
        return
    ctx.metric("decision.conditions", ", ".join(c.code for c in d.conditions))
    hits = _hits(ctx.case, lambda h: h.effect in ("CONDITION", "REDUCE_AMOUNT"))
    lines = [f"- **{c.code}**: {c.text}" for c in d.conditions]
    text = "Conditions:\n" + "\n".join(lines)
    if hits:
        text += "\nTriggered by: " + " ".join(ctx.rule(h) for h in hits[:6])
    ctx.say(text)


def _fraud(ctx: _Ctx) -> None:
    c = ctx.case
    hits = _hits(c, lambda h: h.category in (RuleCategory.FRAUD, RuleCategory.COMPLIANCE, RuleCategory.KYC))
    flags = c.bundle.flags
    if not hits and not flags:
        ctx.say("No fraud, tampering, negative-list or compliance exceptions were found.")
        fr = _hits(c, lambda h: h.category == RuleCategory.FRAUD, non_pass=False)
        if fr:
            ctx.say("Checks passed: " + " ".join(ctx.rule(h) for h in fr[:6]))
        return
    if flags:
        for f in flags[:6]:
            if f.document_id:
                ctx.cite("document", f.document_id, f"{f.code}: {f.detail}")
        ctx.say("Document flags:\n" + "\n".join(f"- {f.code} ({f.severity.value}): {f.detail}" for f in flags[:6]))
    if hits:
        ctx.say("Fraud / compliance rules:\n" + _rule_lines(ctx, hits))


def _missing_docs(ctx: _Ctx) -> None:
    c = ctx.case
    miss = [m.value for m in c.bundle.missing_documents]
    docs = c.bundle.documents
    for d in docs[:10]:
        ctx.cite("document", d.id, f"{d.filename}: {d.doc_type.value} via {d.ocr_engine}")
    ctx.metric("bundle.missing_documents", ", ".join(miss) or "none")
    text = (f"Documents received ({len(docs)}): " + ", ".join(sorted({d.doc_type.value for d in docs})) + ". "
            if docs else "No documents were received. ")
    text += ("Missing: **" + ", ".join(miss) + "** — a request for documents was raised." if miss
             else "No required documents are missing.")
    failed = [cc for cc in c.bundle.cross_checks if not cc.match]
    if failed:
        text += " Cross-check mismatches: " + "; ".join(
            f"{cc.field} ({cc.note or f'score {cc.score:.2f}'})" for cc in failed) + "."
    hits = _hits(c, lambda h: h.category in (RuleCategory.DOCUMENT, RuleCategory.KYC))
    if hits:
        text += "\n" + _rule_lines(ctx, hits)
    ctx.say(text)


def _income(ctx: _Ctx) -> None:
    c = ctx.case
    e, b, f = c.eligibility, c.bank, c.form
    ctx.metric("eligibility.assessed_income", inr(e.assessed_income))
    parts = [f"declared {inr(f.declared_monthly_income)}", f"bank-evidenced {inr(b.income_estimate)}"]
    if b.avg_salary_credit:
        parts.append(f"average salary credit {inr(b.avg_salary_credit)}")
    if c.bundle.salary_slips:
        nets = [float(s.get("net", 0) or 0) for s in c.bundle.salary_slips]
        parts.append(f"salary-slip net pay {inr(sum(nets) / len(nets))}")
    ann = c.bundle.income_docs.get("annual_income") if c.bundle.income_docs else None
    if ann:
        parts.append(f"ITR/Form 16 {inr(float(ann) / 12)}/month")
    if f.co_applicant:
        parts.append(f"co-applicant {f.co_applicant.name} {inr(f.co_applicant.monthly_net_income)}")
    text = (f"Income used for eligibility is **{inr(e.assessed_income)}/month** ({e.income_basis}). "
            f"Evidence: {', '.join(parts)}.")
    hits = _hits(c, lambda h: _has(h, "income", "inflat", "salary"))
    if hits:
        text += "\n" + _rule_lines(ctx, hits, 4)
    ctx.say(text)


def _bank(ctx: _Ctx) -> None:
    b = ctx.case.bank
    ctx.metric("bank.bounces", str(b.bounces))
    ctx.metric("bank.avg_monthly_balance", inr(b.avg_monthly_balance))
    text = (f"Bank statement: {b.months_covered:g} months, average balance {inr(b.avg_monthly_balance)}, "
            f"**{b.bounces} bounce(s)**, salary regularity {pct(b.salary_regularity, 0)}, "
            f"{len(b.detected_emis)} existing EMI(s) totalling {inr(b.total_detected_emi)}/month.")
    if b.bounce_details:
        text += " Bounces: " + "; ".join(
            f"{x.get('date', '')} {x.get('description', '')} {inr(abs(float(x.get('amount', 0) or 0)))}".strip()
            for x in b.bounce_details[:4]) + "."
    if b.cash_deposit_spikes:
        text += f" {len(b.cash_deposit_spikes)} cash-deposit spike(s)."
    if b.high_risk_merchants:
        names = sorted({str(m.get('merchant') or m.get('description') or '') for m in b.high_risk_merchants})
        text += f" High-risk merchant debits: {', '.join(n for n in names if n)[:160]}."
    hits = _hits(ctx.case, lambda h: h.category == RuleCategory.BANKING or _has(h, "bounce", "bank", "cash"))
    if hits:
        text += "\n" + _rule_lines(ctx, hits, 5)
    ctx.say(text)


def _risk(ctx: _Ctx) -> None:
    r = ctx.case.risk
    ctx.metric("risk.pd", pct(r.pd, 2))
    ctx.metric("risk.grade", r.grade)
    text = (f"Model {r.model_version}: PD **{pct(r.pd, 2)}**, score {r.score}, grade **{r.grade}** ({r.band}); "
            f"ML-only suggestion {ctx.case.decision.model_suggested.value}. Bureau score: {ctx.case.form.bureau_score or 'n/a'}.")
    if r.reasons:
        text += "\nTop risk drivers (SHAP):\n" + "\n".join(
            f"- {s.label} = {s.value}: {'raises' if s.impact > 0 else 'lowers'} risk ({s.impact:+.2f}). {s.text}"
            for s in r.reasons[:5])
    hits = _hits(ctx.case, lambda h: h.category == RuleCategory.RISK or _has(h, "bureau"))
    if hits:
        text += "\n" + _rule_lines(ctx, hits, 4)
    ctx.say(text)


def _capacity(ctx: _Ctx) -> None:
    cap = ctx.case.capacity
    ctx.metric("capacity.prob_shortfall", pct(cap.prob_shortfall))
    ctx.metric("capacity.health_score", f"{cap.health_score:.0f}")
    lim = _policy_raw().get("capacity", {}).get("max_prob_shortfall")
    if lim is not None:
        ctx.cite("policy", "capacity.max_prob_shortfall", pct(float(lim), 0))
    text = (f"Repayment capacity: health score **{cap.health_score:.0f}/100**, surplus after EMI "
            f"{inr(cap.monthly_surplus_after_emi)}/month, probability of a cash shortfall **{pct(cap.prob_shortfall)}** "
            f"across {cap.iterations} Monte Carlo paths"
            + (f" (policy limit {pct(float(lim), 0)})" if lim is not None else "")
            + f", stress coverage {cap.stress_emi_coverage:.2f}x under +200 bps and −15% income.")
    if cap.forecast:
        last = cap.forecast[-1]
        text += f" Month {last.month} buffer: P10 {inr(last.p10)}, P50 {inr(last.p50)}, P90 {inr(last.p90)}."
    hits = _hits(ctx.case, lambda h: h.category == RuleCategory.CAPACITY)
    if hits:
        text += "\n" + _rule_lines(ctx, hits, 3)
    ctx.say(text)


def _rate(ctx: _Ctx) -> None:
    c = ctx.case
    pr = _policy_raw().get("pricing", {})
    product_key = "base_rate_home_loan" if c.form.product.value == "HOME_LOAN" else "base_rate_lap"
    base = pr.get(product_key)
    spread = pr.get("grade_spread", {}).get(c.risk.grade)
    rate = c.decision.rate or c.eligibility.rate
    ctx.metric("decision.rate", pct(rate, 2))
    if base is not None:
        ctx.cite("policy", f"pricing.{product_key}", pct(float(base), 2))
    text = f"Rate applied: **{pct(rate, 2)} p.a.** ({c.form.rate_type.lower()})"
    if base is not None and spread is not None:
        ctx.cite("policy", f"pricing.grade_spread.{c.risk.grade}", pct(float(spread), 2))
        text += f" = base {pct(float(base), 2)} + grade {c.risk.grade} spread {pct(float(spread), 2)}"
        if c.form.employment_type.value == "SELF_EMPLOYED" and pr.get("self_employed_spread") is not None:
            text += f" + self-employed spread {pct(float(pr['self_employed_spread']), 2)}"
    ctx.say(text + ".")


def _policy_general(ctx: _Ctx) -> None:
    pol = _policy_raw()
    e = ctx.case.eligibility
    ctx.cite("policy", "version", str(pol.get("version", "")))
    ctx.say(f"Policy {pol.get('version', e.policy_version)}: FOIR cap {pct(e.foir_cap, 0)} for this income band, "
            f"LTV cap {pct(e.ltv_cap, 0)} {ctx.ref(e.ltv_rule_id)}, max tenure {e.max_tenure_months} months. "
            "Ask about any rule by its ID (e.g. ELG-FOIR-02) for its threshold and reference.")


def _rule_lookup(ctx: _Ctx, ids: list[str]) -> None:
    idx = policy_rule_index()
    pol = _policy_raw()
    refs = pol.get("references", {})
    for rid in ids:
        hit = next((h for h in ctx.case.decision.rules_fired if h.rule_id == rid), None)
        pr = idx.get(rid)
        if not hit and not pr:
            ctx.say(f"Rule {rid} does not exist in policy {pol.get('version', '')} and was not evaluated on this case.")
            continue
        parts: list[str] = []
        if hit:
            parts.append(f"{ctx.rule(hit)} **{hit.name}** — {hit.outcome.value} (effect {hit.effect}): {hit.detail}")
            if hit.evidence:
                ev = ", ".join(f"{k}={v}" for k, v in list(hit.evidence.items())[:6])
                parts.append(f"Evidence: {ev}.")
            if hit.reference:
                parts.append(f"Reference: {hit.reference}.")
        if pr:
            vals = ", ".join(f"{k}={v}" for k, v in pr.items() if k not in ("id", "path", "ref"))
            ref_key = pr.get("ref")
            if not hit:
                ctx.cite("rule", rid, f"policy {pr['path']}: {vals}")
                parts.append(f"[{rid}] is defined at `{pr['path']}` ({vals}); it was not triggered as an exception on this case.")
            else:
                ctx.cite("policy", pr["path"], vals)
                parts.append(f"Policy definition `{pr['path']}`: {vals}.")
            if ref_key and ref_key in refs:
                ctx.cite("policy", f"references.{ref_key}", str(refs[ref_key]))
                parts.append(f"Regulatory basis: {refs[ref_key]}.")
        ctx.say(" ".join(parts))


# --------------------------------------------------------------------------- what-if
_AMT_RE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:[.,]\d+)*)\s*(crores?|cr|lakhs?|lacs?|lac|l|k|thousand)?\b", re.I)
_TEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|y|months?|mths?|m)\b", re.I)


def _to_amount(num: str, unit: str | None) -> float:
    v = float(num.replace(",", ""))
    u = (unit or "").lower()
    if u.startswith("cr"):
        return v * 1e7
    if u.startswith("l"):
        return v * 1e5
    if u in ("k", "thousand"):
        return v * 1e3
    return v


def parse_what_if(q: str, case: CaseDetail) -> dict[str, Any]:
    """Extract amount / tenure / co-applicant income from a what-if question."""
    out: dict[str, Any] = {}
    ql = q.lower()
    for m in _TEN_RE.finditer(ql):
        n = float(m.group(1))
        out["tenure_months"] = round(n * 12) if m.group(2).startswith("y") else round(n)
    spans = [m.span() for m in _TEN_RE.finditer(ql)]
    amounts: list[tuple[float, int]] = []
    for m in _AMT_RE.finditer(ql):
        if any(s <= m.start(1) < e for s, e in spans):
            continue
        amt = _to_amount(m.group(1), m.group(2))
        has_marker = bool(m.group(2)) or bool(re.match(r"\s*(?:₹|rs|inr)", ql[m.start():m.start(1)] or ""))
        if has_marker or amt >= 10000:
            amounts.append((amt, m.start()))
    co = re.search(r"co.?applicant[^.?]*", ql)
    if co and amounts:
        for amt, pos in amounts:
            if co.start() <= pos <= co.end():
                out["extra_income"] = amt
                amounts = [a for a in amounts if a[1] != pos]
                break
    if amounts:
        amt, pos = amounts[0]
        before = ql[max(0, pos - 40):pos]
        if re.search(r"\bby\s*$", before):
            sign = -1 if re.search(r"reduc|lower|cut|decreas|less", before) else 1
            amt = case.eligibility.requested_amount + sign * amt
        out["amount"] = amt
    return out


def _what_if(ctx: _Ctx, q: str) -> bool:
    from app.engine.finance import emi as calc_emi
    c = ctx.case
    e = c.eligibility
    p = parse_what_if(q, c)
    if not p:
        return False
    amt = float(p.get("amount", e.requested_amount))
    months = int(p.get("tenure_months", c.form.tenure_months))
    income = e.assessed_income + float(p.get("extra_income", 0))
    rate = c.decision.rate or e.rate
    new_emi = float(calc_emi(amt, rate, months))
    foir = (e.existing_obligations + new_emi) / income if income > 0 else float("inf")
    policy = _policy()
    try:
        foir_id, foir_cap = policy.foir_cap(income)
    except Exception:
        foir_id, foir_cap = "", e.foir_cap
    basis = e.requested_amount / e.ltv_actual if e.ltv_actual > 0 else c.form.property_value
    ltv = amt / basis if basis > 0 else 0.0
    try:
        ltv_id, ltv_cap, _ = policy.ltv_cap(c.form.product.value, amt, c.form.property_type)
    except Exception:
        ltv_id, ltv_cap = e.ltv_rule_id, e.ltv_cap
    foir_cap = float(foir_cap)
    ltv_cap = float(ltv_cap)
    if foir_id:
        ctx.cite("rule", str(foir_id), f"FOIR cap {pct(foir_cap, 0)} for income {inr(income)}/month")
    if ltv_id:
        ctx.cite("rule", str(ltv_id), f"LTV cap {pct(ltv_cap, 0)} for {inr(amt)}")
    ctx.metric("what_if.emi", inr(new_emi))
    ctx.metric("what_if.foir", pct(foir))
    ctx.metric("what_if.ltv", pct(ltv))
    checks = [
        f"FOIR {pct(foir)} vs cap {pct(foir_cap, 0)} [{foir_id}] → {'OK' if foir <= foir_cap else 'BREACH'}",
        f"LTV {pct(ltv)} vs cap {pct(ltv_cap, 0)} [{ltv_id}] → {'OK' if ltv <= ltv_cap + 1e-9 else 'BREACH'}",
        f"tenure {months} vs max {e.max_tenure_months} months → "
        f"{'OK' if months <= e.max_tenure_months else 'BREACH (age at maturity / product limit)'}",
    ]
    scen = f"{inr(amt)} over {months} months at {pct(rate, 2)}"
    if p.get("extra_income"):
        scen += f" with {inr(p['extra_income'])}/month extra co-applicant income"
    passes = foir <= foir_cap and ltv <= ltv_cap + 1e-9 and months <= e.max_tenure_months
    text = (f"What-if — {scen}: EMI **{inr(new_emi)}**.\n" + "\n".join(f"- {x}" for x in checks)
            + f"\nOn eligibility parameters this scenario {'passes' if passes else 'does not pass'}.")
    other = _hits(c, lambda h: h.effect in ("DECLINE", "REFER") and not _has(h, "foir", "ltv", "tenure", "age"))
    if other:
        text += (" Note: the outcome also depends on non-eligibility rules that this change does not fix: "
                 + " ".join(dict.fromkeys(ctx.rule(h) for h in other[:8])) + ".")
    text += " (Indicative recomputation; the engine re-runs all rules on resubmission.)"
    ctx.say(text)
    return True


# --------------------------------------------------------------------------- router
_HANDLERS: dict[str, Callable[[_Ctx], None]] = {
    "decision": _decision, "foir": _foir, "ltv": _ltv, "max_eligible": _max_eligible, "emi": _emi,
    "conditions": _conditions, "fraud": _fraud, "missing_docs": _missing_docs, "income": _income,
    "bank": _bank, "risk": _risk, "capacity": _capacity, "rate": _rate, "policy": _policy_general,
}


def route(question: str) -> list[str]:
    q = question.lower()
    intents = [name for name, pat in INTENT_PATTERNS if re.search(pat, q)]
    if "decision" in intents and len(intents) > 1 and not _SPECIFIC_DECISION.search(q):
        intents.remove("decision")  # a bare "why" belongs to the specific topic asked
    if "policy" in intents and len(intents) > 1:
        intents.remove("policy")
    return intents


def template_answer(case: CaseDetail, question: str) -> tuple[CopilotAnswer, list[str]]:
    q = question.strip()
    if _PII.search(q):
        return CopilotAnswer(answer=PII_REFUSAL, grounded=True), ["pii_refusal"]
    if _OUT_OF_SCOPE.search(q):
        return CopilotAnswer(answer=REFUSAL, grounded=True), ["out_of_scope"]
    ctx = _Ctx(case)
    ids = list(dict.fromkeys(RULE_ID_RE.findall(q.upper())))
    intents = route(RULE_ID_RE.sub(" ", q) if ids else q)
    if ids:
        _rule_lookup(ctx, ids)
        intents = [i for i in intents if i not in ("policy", "decision")]
    if "what_if" in intents:
        intents.remove("what_if")
        if _what_if(ctx, q):
            intents = [i for i in intents if i not in ("emi", "foir", "ltv", "decision", "max_eligible")]
        elif not intents:
            intents = ["max_eligible"]
    for name in intents[:4]:
        _HANDLERS[name](ctx)
    if not ctx.paras:
        return CopilotAnswer(answer=REFUSAL, grounded=True), ["out_of_scope"]
    used = (["rule_lookup"] if ids else []) + intents[:4]
    return CopilotAnswer(answer="\n\n".join(ctx.paras), citations=ctx.cites), used


# --------------------------------------------------------------------------- LLM rephrase + verification
_SYSTEM = (
    "You are the Underwriting Copilot for a housing-finance credit underwriter. Answer the question using ONLY "
    "the FACTS provided. Do not add any number, rule, document or policy that is not in the FACTS. Cite every "
    "rule you rely on by its ID in square brackets exactly as written in the FACTS (e.g. [ELG-FOIR-01]). "
    "If the FACTS do not answer the question, say so. Never reveal personal identifiers. Be concise (under 150 "
    "words), professional and plain-English."
)


def _norm_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM_RE.findall(text):
        n = m.replace(",", "").rstrip(".")
        if not n:
            continue
        out.add(n)
        if "." in n:
            out.add(n.rstrip("0").rstrip("."))
    return out


def verify_llm_answer(draft: str, facts: str, known: set[str], require_rule: bool) -> tuple[bool, str]:
    cited = set(RULE_ID_RE.findall(draft))
    unknown = sorted(cited - known)
    if unknown:
        return False, f"cites unknown rule id(s) {unknown}"
    if require_rule and not cited:
        return False, "no rule ids cited"
    fact_nums = _norm_numbers(facts)
    bad = [n for n in _norm_numbers(draft) if len(n.replace(".", "")) >= 2 and n not in fact_nums]
    if bad:
        return False, f"numbers not in facts {bad[:5]}"
    return True, "ok"


def _redact(text: str) -> str:
    try:
        from app.engine.masking import redact_text
        return str(redact_text(text))
    except ImportError:  # pragma: no cover
        return text


def answer(case: CaseDetail, question: str, provider: LLMProvider | bool | None = True) -> CopilotAnswer:
    """Answer ``question`` about ``case``. ``provider=True`` auto-detects an LLM; ``None``/``False`` disables it."""
    tmpl, intents = template_answer(case, question)
    tmpl.answer = _redact(tmpl.answer)
    if intents and intents[0] in ("out_of_scope", "pii_refusal"):
        return tmpl
    llm = get_provider() if provider is True else (provider or None)
    if not llm:
        return tmpl
    facts = tmpl.answer + "\n\nCITED FACTS:\n" + "\n".join(f"- [{c.ref}] ({c.kind}) {c.text}" for c in tmpl.citations)
    try:
        draft = llm.complete(_SYSTEM, f"QUESTION: {question}\n\nFACTS:\n{facts}")
    except Exception as exc:
        log.info("LLM failed (%s); using grounded template", exc)
        return tmpl
    known = known_rule_ids(case) & ({c.ref for c in tmpl.citations} | set(RULE_ID_RE.findall(facts)))
    ok, why = verify_llm_answer(draft, facts, known,
                                require_rule=any(c.kind == "rule" for c in tmpl.citations))
    if not ok or not draft:
        log.info("LLM draft rejected: %s", why)
        return tmpl
    return CopilotAnswer(answer=_redact(draft), citations=tmpl.citations, engine=llm.label, grounded=True)
