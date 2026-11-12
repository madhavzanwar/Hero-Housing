"""Hybrid decisioning: policy rules dominate, the ML PD grade refines (RBI FREE-AI: human oversight).

Precedence: any DECLINE effect -> DECLINE; any REFER effect (rules, grade D/E, amount above the
auto-approval limit, capacity) -> REFER; reduce-amount / conditions / grade C -> APPROVE_WITH_CONDITIONS;
otherwise APPROVE. Sanctioned amount = min(requested, max eligible at the risk-based rate), rounded
down to Rs 10,000; EMI is recomputed at the final amount, rate and tenure.
"""
from __future__ import annotations

import math
from datetime import datetime

from app.engine.finance import emi, fmt_inr, pct, principal_from_emi, round_down
from app.engine.pricing import rate_for
from app.engine.rules import hit
from app.policy.loader import Policy
from app.schemas import (
    ApplicationForm,
    Condition,
    Decision,
    DecisionOutcome,
    DocumentBundle,
    Eligibility,
    Product,
    RepaymentCapacity,
    RiskScore,
    RuleHit,
    RuleOutcome,
    Severity,
)

D = DecisionOutcome
OC = RuleOutcome
S = Severity
_SEV_ORDER = {S.CRITICAL: 0, S.HIGH: 1, S.MEDIUM: 2, S.LOW: 3, S.INFO: 4}


def model_action(grade: str, policy: Policy) -> DecisionOutcome:
    for band in policy.get("risk.pd_bands", []):
        if band.get("grade") == grade:
            return D(band.get("action", "REFER"))
    return D.REFER


def _additional_income_needed(policy: Policy, income: float, obligations: float, target_emi: float) -> float:
    """Extra monthly income (co-applicant) so that (obligations + EMI) / income <= FOIR cap (band-aware)."""
    need = obligations + target_emi
    inc = income
    for _ in range(8):
        _, cap = policy.foir_cap(inc)
        required = need / cap
        if required <= inc + 1:
            break
        inc = required
    extra = max(0.0, inc - income)
    return float(math.ceil(extra / 100.0) * 100) if extra > 0 else 0.0


def _risk_hit(risk: RiskScore, policy: Policy, other_decline: bool) -> RuleHit:
    top = risk.reasons[0].text if risk.reasons else ""
    base = (f"Model probability of default is {pct(risk.pd)} (grade {risk.grade}, {risk.band} risk)"
            + (f"; main driver: {top.rstrip('.')}." if top else "."))
    ev = {"pd": risk.pd, "grade": risk.grade, "score": risk.score, "model_version": risk.model_version}
    if risk.grade in ("A", "B"):
        return hit(policy, "RSK-PD-01", OC.PASS, base, evidence=ev)
    if risk.grade == "C":
        return hit(policy, "RSK-PD-01", OC.WARN, base + " Priced with the grade spread and NACH mandate.",
                   effect="CONDITION", severity=S.MEDIUM, evidence={**ev, "condition": "RISK_PRICING"})
    if risk.grade == "D":
        return hit(policy, "RSK-PD-01", OC.WARN, base + " Underwriter review required.", effect="REFER",
                   severity=S.HIGH, evidence=ev)
    if policy.get("risk.model_decline_becomes_refer", True) and not other_decline:
        return hit(policy, "RSK-PD-01", OC.FAIL, base + " The model alone would decline; referred so that a human decides.",
                   effect="REFER", severity=S.HIGH, evidence=ev)
    return hit(policy, "RSK-PD-01", OC.FAIL, base, effect="DECLINE", severity=S.HIGH, evidence=ev)


def _capacity_hits(capacity: RepaymentCapacity | None, policy: Policy) -> list[RuleHit]:
    if capacity is None:
        return []
    c = policy.section("capacity")
    mx, ref = float(c.get("max_prob_shortfall", 0.2)), float(c.get("refer_prob_shortfall", 0.4))
    ev = {"prob_shortfall": capacity.prob_shortfall, "surplus_after_emi": capacity.monthly_surplus_after_emi,
          "health_score": capacity.health_score, "iterations": capacity.iterations}
    out: list[RuleHit] = []
    if capacity.prob_shortfall > ref:
        out.append(hit(policy, "CAP-MC-01", OC.FAIL,
                       f"Monte Carlo simulation ({capacity.iterations} runs) shows a {pct(capacity.prob_shortfall, 0)} chance "
                       f"that the bank buffer turns negative within the horizon after paying the EMI.",
                       effect="REFER", severity=S.HIGH, evidence=ev))
    elif capacity.prob_shortfall > mx:
        out.append(hit(policy, "CAP-MC-01", OC.WARN,
                       f"Monte Carlo simulation shows a {pct(capacity.prob_shortfall, 0)} chance of a cash shortfall "
                       f"(limit {pct(mx, 0)}); an EMI reserve is required.",
                       effect="CONDITION", severity=S.MEDIUM, evidence={**ev, "condition": "EMI_RESERVE"}))
    else:
        out.append(hit(policy, "CAP-MC-01", OC.PASS,
                       f"Repayment buffer stays positive in {pct(1 - capacity.prob_shortfall, 0)} of {capacity.iterations} "
                       f"simulated paths; surplus after EMI {fmt_inr(capacity.monthly_surplus_after_emi)} a month.",
                       evidence=ev))
    min_cov = float(c.get("min_stress_coverage", 1.0))
    sev = {"stress_emi_coverage": capacity.stress_emi_coverage, "min": min_cov}
    if capacity.stress_emi_coverage < min_cov:
        out.append(hit(policy, "CAP-STR-01", OC.WARN,
                       f"Under a +{int(c.get('rate_shock_bps', 200))} bps rate shock and "
                       f"{pct(float(c.get('income_shock_pct', 0.15)), 0)} "
                       f"income drop, surplus covers the EMI only {capacity.stress_emi_coverage:.2f}x.",
                       severity=S.LOW, evidence=sev))
    else:
        out.append(hit(policy, "CAP-STR-01", OC.PASS,
                       f"Stress test passed: surplus covers the shocked EMI {capacity.stress_emi_coverage:.2f}x.", evidence=sev))
    return out


def decide(
    form: ApplicationForm,
    eligibility: Eligibility,
    risk: RiskScore,
    capacity: RepaymentCapacity | None,
    rule_hits: list[RuleHit],
    bundle: DocumentBundle,
    policy: Policy,
    started_at: datetime,
) -> Decision:
    dcfg = policy.section("decision")
    catalogue: dict[str, str] = dict(dcfg.get("conditions_catalogue", {}))
    step = float(dcfg.get("amount_rounding", 10000))
    min_share = float(dcfg.get("min_reduced_share", 0.5))
    requested = float(form.loan_amount)

    rate = rate_for(form, risk.grade, policy)
    tenure = eligibility.tenure_months or min(form.tenure_months, eligibility.max_tenure_months)
    tenure = max(int(tenure), 1)
    max_emi = eligibility.max_emi_affordable
    foir_loan = principal_from_emi(max_emi, rate, tenure)
    caps = [foir_loan, eligibility.max_loan_by_ltv]
    if form.product == Product.LAP:
        caps.append(float(policy.get("lap.max_loan", 5e7)))
    max_final = max(0.0, min(caps))

    hits: list[RuleHit] = list(rule_hits)
    income, oblig = eligibility.assessed_income, eligibility.existing_obligations
    foir_id, foir_cap = policy.foir_cap(income)
    foir_failed = any(h.rule_id.startswith("ELG-FOIR") and h.outcome == OC.FAIL for h in hits)
    if not foir_failed and requested > foir_loan + 1 and income > 0:
        e_req = emi(requested, rate, tenure)
        foir_at_rate = (oblig + e_req) / income
        feasible = max_final >= min_share * requested
        hits.append(hit(policy, foir_id, OC.FAIL,
                        f"At the risk-based rate of {pct(rate, 2)} the EMI rises to {fmt_inr(e_req)} and FOIR to "
                        f"{pct(foir_at_rate)}, above the {pct(foir_cap, 0)} cap; income supports {fmt_inr(foir_loan)}.",
                        effect="REDUCE_AMOUNT" if feasible else "DECLINE", severity=S.MEDIUM,
                        evidence={"rate": rate, "foir": round(foir_at_rate, 4), "cap": foir_cap,
                                  "max_loan_by_foir": round(foir_loan, 2)}))

    pre_decline = any(h.effect == "DECLINE" for h in hits)
    hits.append(_risk_hit(risk, policy, pre_decline))
    hits.extend(_capacity_hits(capacity, policy))
    auto_max = float(dcfg.get("auto_approve_max_amount", 2e7))
    if requested > auto_max:
        hits.append(hit(policy, "DEC-AMT-01", OC.WARN,
                        f"Requested {fmt_inr(requested)} is above the auto-approval limit of {fmt_inr(auto_max)}; "
                        f"a credit committee decision is required.", effect="REFER", severity=S.MEDIUM,
                        evidence={"requested": requested, "limit": auto_max}))

    # ------------------------------------------------------------ amount
    sanction = round_down(min(requested, max_final), step) if requested > max_final + 1 else requested
    declines = [h for h in hits if h.effect == "DECLINE"]
    refers = [h for h in hits if h.effect == "REFER"]
    reduces = [h for h in hits if h.effect == "REDUCE_AMOUNT"]
    if sanction <= 0 or (sanction < min_share * requested and not declines):
        declines.append(hit(policy, foir_id if foir_loan <= eligibility.max_loan_by_ltv else eligibility.ltv_rule_id,
                            OC.FAIL, f"The maximum eligible amount of {fmt_inr(max_final)} is less than "
                            f"{pct(min_share, 0)} of the {fmt_inr(requested)} requested.",
                            effect="DECLINE", severity=S.HIGH, evidence={"max_eligible": round(max_final, 2)}))
        hits.append(declines[-1])

    # ------------------------------------------------------------ conditions
    conditions: list[Condition] = []
    if sanction < requested and not declines:
        ltv_binding = eligibility.max_loan_by_ltv <= foir_loan
        why = (f"LTV cap of {pct(eligibility.ltv_cap, 0)} on property value {fmt_inr(eligibility.property_value)}"
               if ltv_binding else f"FOIR cap of {pct(foir_cap, 0)} on income {fmt_inr(income)}")
        conditions.append(Condition(
            code="REDUCE_AMOUNT",
            text=f"Reduce the loan amount to {fmt_inr(sanction)} (from {fmt_inr(requested)}) to stay within the {why}"
                 + ("; the balance must come from own contribution." if ltv_binding else "."),
            params={"amount": sanction, "requested": requested, "binding": "LTV" if ltv_binding else "FOIR"}))
        if not ltv_binding and requested <= eligibility.max_loan_by_ltv:
            target_emi = emi(requested, rate, tenure)
            extra = _additional_income_needed(policy, income, oblig, target_emi)
            if extra > 0:
                conditions.append(Condition(
                    code="ADD_CO_APPLICANT",
                    text=f"Alternatively, add an earning co-applicant with net income of at least {fmt_inr(extra)} a month "
                         f"to keep the full {fmt_inr(requested)}.",
                    params={"additional_income": extra, "alternative": True}))
            for opt in sorted({o.tenure_months for o in eligibility.tenure_options} | {eligibility.max_tenure_months}):
                if opt <= tenure or opt > eligibility.max_tenure_months:
                    continue
                if principal_from_emi(max_emi, rate, opt) >= requested:
                    conditions.append(Condition(
                        code="INCREASE_TENURE",
                        text=f"Alternatively, increase the tenure to {opt} months (EMI {fmt_inr(emi(requested, rate, opt))}) "
                             f"to keep the full amount within FOIR.",
                        params={"tenure_months": opt, "emi": round(emi(requested, rate, opt), 2), "alternative": True}))
                    break
            if oblig > 0 and target_emi <= foir_cap * income:
                conditions.append(Condition(
                    code="CLEAR_EMI",
                    text=f"Alternatively, close existing loans with EMIs of {fmt_inr(oblig)} a month before disbursal.",
                    params={"existing_emi": oblig, "alternative": True}))
    seen_codes = {c.code for c in conditions}
    for h in hits:
        code = h.evidence.get("condition") if h.effect == "CONDITION" else None
        if not code or h.outcome == OC.PASS:
            continue
        if code in seen_codes:
            for c in conditions:
                if c.code == code:
                    c.params.setdefault("rules", []).append(h.rule_id)
            continue
        seen_codes.add(code)
        text = catalogue.get(code, code.replace("_", " ").capitalize())
        if code == "SUBMIT_DOC" and h.evidence.get("items"):
            text = "Submit: " + ", ".join(h.evidence["items"]) + "."
        elif code == "REDUCE_TENURE":
            text = f"Tenure restricted to {eligibility.max_tenure_months} months so that the loan matures by the maximum age."
        else:
            text = f"{text}. {h.detail}" if not text.endswith(".") else f"{text} {h.detail}"
        conditions.append(Condition(code=code, text=text, params={"rules": [h.rule_id]}))

    # ------------------------------------------------------------ outcome
    if declines:
        outcome = D.DECLINE
    elif refers:
        outcome = D.REFER
    elif reduces or conditions or sanction < requested:
        outcome = D.APPROVE_WITH_CONDITIONS
    else:
        outcome = D.APPROVE
    if outcome == D.DECLINE:
        sanction, final_emi, conditions = 0.0, 0.0, []
    else:
        final_emi = round(emi(sanction, rate, tenure), 2)

    # ------------------------------------------------------------ reasons
    def _ordered(items: list[RuleHit]) -> list[RuleHit]:
        return sorted(items, key=lambda h: _SEV_ORDER.get(h.severity, 5))

    reasons: list[str] = []
    if outcome == D.DECLINE:
        reasons.append(f"Application declined: {len(declines)} policy rule(s) cannot be met.")
        reasons += [h.detail for h in _ordered(declines)]
    elif outcome == D.REFER:
        reasons.append(f"Referred to an underwriter: {len(refers)} item(s) need human review; provisional amount "
                       f"{fmt_inr(sanction)} over {tenure} months at {pct(rate, 2)}.")
        reasons += [h.detail for h in _ordered(refers)]
    else:
        head = "Approved" if outcome == D.APPROVE else "Approved with conditions"
        reasons.append(f"{head} for {fmt_inr(sanction)} over {tenure} months at {pct(rate, 2)} (EMI {fmt_inr(final_emi)}).")
        reasons += [h.detail for h in _ordered(reduces)]
        reasons += [h.detail for h in _ordered([h for h in hits if h.effect == "CONDITION" and h.outcome != OC.PASS])]
        foir_final = (oblig + final_emi) / income if income else 0.0
        reasons.append(f"FOIR at the sanctioned amount is {pct(foir_final)} (cap {pct(foir_cap, 0)}); LTV is "
                       f"{pct(sanction / eligibility.property_value if eligibility.property_value else 0)} "
                       f"(cap {pct(eligibility.ltv_cap, 0)}).")
        reasons.append(f"Model risk grade {risk.grade} ({pct(risk.pd)} probability of default).")
    reasons = list(dict.fromkeys(reasons))[:5]

    now = datetime.now(started_at.tzinfo) if started_at.tzinfo else datetime.now()
    return Decision(
        outcome=outcome,
        engine_outcome=outcome,
        model_suggested=model_action(risk.grade, policy),
        sanctioned_amount=float(sanction),
        tenure_months=tenure if outcome != D.DECLINE else 0,
        rate=rate,
        emi=final_emi,
        reasons=reasons,
        conditions=conditions,
        rules_fired=hits,
        decided_by="engine",
        decided_at=now,
        turnaround_ms=max(0, int((now - started_at).total_seconds() * 1000)),
        policy_version=policy.version,
    )
