"""Eligibility: income assessment, FOIR, LTV, tenure and maximum loan, plus banking-conduct rules.

Indian HFC practice (thresholds from policy YAML):
* Income (salaried) = min(declared, avg net pay on slips, avg salary credit in bank).
* Income (self-employed) = min(declared, ITR income/12 x (1 - haircut), bank-credit income estimate).
* Co-applicant income is added (x co_applicant_income_weight); their EMIs are added to obligations.
* Obligations = max(declared EMIs, EMIs detected in the bank statement) + co-applicant EMIs.
* FOIR = (obligations + proposed EMI) / assessed income, capped by income band.
* LTV = loan / min(agreement value, technical valuation); RBI slabs for home loans, internal caps for LAP.
* Max tenure = min(product max, months until max age at maturity).
* Max loan = min(FOIR-based principal at rate & tenure, LTV-based, LAP max).
"""
from __future__ import annotations

import statistics
from datetime import date
from typing import Any

from app.engine.finance import age_on, emi, fmt_inr, pct, principal_from_emi
from app.engine.rules import hit
from app.policy.loader import Policy
from app.schemas import (
    ApplicationForm,
    BankAnalytics,
    DocumentBundle,
    Eligibility,
    EmploymentType,
    Product,
    RuleHit,
    RuleOutcome,
    Severity,
    TenureOption,
)

OC = RuleOutcome
S = Severity


def _parse_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def applicant_dob(form: ApplicationForm, bundle: DocumentBundle) -> date | None:
    return form.dob or _parse_date(bundle.identity.get("dob"))


def slip_net_average(bundle: DocumentBundle) -> float:
    nets = [float(s["net"]) for s in bundle.salary_slips if s.get("net")]
    return statistics.fmean(nets) if nets else 0.0


def itr_monthly(bundle: DocumentBundle) -> float:
    """Average of up to the last two assessment years' total income / 12 (0 if no ITR)."""
    docs = bundle.income_docs or {}
    if str(docs.get("type", "ITR")).upper() != "ITR":
        return 0.0
    years = [y for y in docs.get("years", []) or [] if y.get("total_income")]
    if years:
        years = sorted(years, key=lambda y: str(y.get("ay", "")))[-2:]
        return statistics.fmean(float(y["total_income"]) for y in years) / 12.0
    if docs.get("annual_income"):
        return float(docs["annual_income"]) / 12.0
    return 0.0


def income_evidence(form: ApplicationForm, bundle: DocumentBundle, bank: BankAnalytics, policy: Policy) -> dict[str, Any]:
    """Applicant (not co-applicant) income sources and the assessed figure."""
    declared = float(form.declared_monthly_income)
    sources: dict[str, float] = {"declared": declared}
    if form.employment_type == EmploymentType.SALARIED:
        slip = slip_net_average(bundle)
        if slip > 0:
            sources["salary_slips_net"] = slip
        if bank.avg_salary_credit > 0:
            sources["bank_salary_credit"] = bank.avg_salary_credit
        basis = "minimum of declared income, average net pay on salary slips and average bank salary credit"
        evidenced = bank.avg_salary_credit or slip or 0.0
    else:
        haircut = float(policy.get("eligibility.self_employed_income_haircut", 0.10))
        itr = itr_monthly(bundle)
        if itr > 0:
            sources["itr_monthly_after_haircut"] = itr * (1 - haircut)
        if bank.income_estimate > 0:
            sources["bank_credit_income"] = bank.income_estimate
        basis = f"minimum of declared income, ITR income / 12 less {pct(haircut, 0)} haircut and bank-credit income"
        evidenced = itr or bank.income_estimate or 0.0
    assessed = min(sources.values())
    return {"sources": sources, "assessed": assessed, "basis": basis, "evidenced": evidenced, "declared": declared}


def property_value_basis(form: ApplicationForm, bundle: DocumentBundle) -> tuple[float, dict[str, float]]:
    prop = bundle.property or {}
    vals: dict[str, float] = {}
    valuation = float(prop.get("market_value") or 0)
    if form.product == Product.LAP:
        vals["declared_value"] = float(form.property_value)
        if valuation > 0:
            vals["technical_valuation"] = valuation
            return valuation, vals
        return float(form.property_value), vals
    agreement = float(prop.get("consideration_value") or 0) or float(form.property_value)
    vals["agreement_value"] = agreement
    if valuation > 0:
        vals["technical_valuation"] = valuation
    return min(vals.values()), vals


def max_tenure(form: ApplicationForm, dob: date | None, policy: Policy, as_of: date | None = None) -> tuple[int, float]:
    """(max tenure months, age now). Age limit uses completed months to the max age."""
    prod_max = int(policy.get(f"eligibility.max_tenure_months.{form.product.value}", 360))
    if dob is None:
        return prod_max, 0.0
    age = age_on(dob, as_of)
    max_age = float(policy.get(f"eligibility.max_age_at_maturity.{form.employment_type.value}", 60))
    months_left = int((max_age - age) * 12)
    return max(0, min(prod_max, months_left)), age


def _cap_loan(form: ApplicationForm, policy: Policy, foir_loan: float, ltv_loan: float) -> float:
    vals = [foir_loan, ltv_loan]
    if form.product == Product.LAP:
        vals.append(float(policy.get("lap.max_loan", 5e7)))
    return max(0.0, min(vals))


def assess(
    form: ApplicationForm,
    bundle: DocumentBundle,
    bank: BankAnalytics,
    policy: Policy,
    rate: float,
    as_of: date | None = None,
) -> tuple[Eligibility, list[RuleHit]]:
    elg = policy.section("eligibility")
    hits: list[RuleHit] = []
    notes: list[str] = []
    emp = form.employment_type.value

    # ------------------------------------------------------------ income & obligations
    inc = income_evidence(form, bundle, bank, policy)
    applicant_income = inc["assessed"]
    co = form.co_applicant
    co_income = float(co.monthly_net_income) * float(elg.get("co_applicant_income_weight", 1.0)) if co else 0.0
    assessed_income = applicant_income + co_income
    basis = inc["basis"] + (f"; plus co-applicant {co.name} {fmt_inr(co_income)}" if co and co_income else "")
    existing = max(float(form.existing_emi), float(bank.total_detected_emi)) + (float(co.existing_emi) if co else 0.0)
    if bank.total_detected_emi > form.existing_emi + 500:
        hits.append(hit(policy, "BNK-EMI-01", OC.WARN,
                        f"Bank statement shows loan EMIs of {fmt_inr(bank.total_detected_emi)} a month against "
                        f"{fmt_inr(form.existing_emi)} declared; the higher figure is used for FOIR.",
                        severity=S.MEDIUM,
                        evidence={"declared_emi": form.existing_emi, "detected_emi": bank.total_detected_emi,
                                  "detected": bank.detected_emis}))

    # ------------------------------------------------------------ age & tenure
    dob = applicant_dob(form, bundle)
    tenure_cap, age = max_tenure(form, dob, policy, as_of)
    min_age = float(elg.get("min_age", 21))
    max_age_mat = float(policy.get(f"eligibility.max_age_at_maturity.{emp}", 60))
    min_tenure = int(elg.get("min_tenure_months", 60))
    if dob is None:
        hits.append(hit(policy, "ELG-AGE-01", OC.WARN, "Date of birth could not be verified from documents.",
                        effect="CONDITION", severity=S.MEDIUM, evidence={"condition": "SUBMIT_DOC"}))
    elif age < min_age:
        hits.append(hit(policy, "ELG-AGE-01", OC.FAIL, f"Applicant is {age:.1f} years old; minimum age is {min_age:.0f}.",
                        effect="DECLINE", severity=S.HIGH, evidence={"age": age, "min_age": min_age}))
    else:
        hits.append(hit(policy, "ELG-AGE-01", OC.PASS, f"Applicant age {age:.1f} years meets the minimum of {min_age:.0f}.",
                        evidence={"age": age}))
    tenure = min(int(form.tenure_months), tenure_cap)
    ten_ev = {"requested_months": form.tenure_months, "max_tenure_months": tenure_cap, "age": age,
              "max_age_at_maturity": max_age_mat}
    if tenure_cap < min_tenure:
        hits.append(hit(policy, "ELG-TEN-01", OC.FAIL,
                        f"At age {age:.0f} only {tenure_cap} months remain before the maximum age at maturity of "
                        f"{max_age_mat:.0f}, below the minimum tenure of {min_tenure} months.",
                        effect="DECLINE", severity=S.HIGH, evidence=ten_ev))
    elif form.tenure_months > tenure_cap:
        hits.append(hit(policy, "ELG-TEN-01", OC.WARN,
                        f"Requested tenure of {form.tenure_months} months is restricted to {tenure_cap} months "
                        f"(loan must mature by age {max_age_mat:.0f} / product maximum).",
                        effect="CONDITION", severity=S.MEDIUM, evidence={**ten_ev, "condition": "REDUCE_TENURE"}))
    else:
        hits.append(hit(policy, "ELG-TEN-01", OC.PASS,
                        f"Tenure of {form.tenure_months} months is within the maximum of {tenure_cap} months.",
                        evidence=ten_ev))
    tenure = max(tenure, 1)
    age_at_maturity = round(age + tenure / 12.0, 1) if dob else 0.0

    # ------------------------------------------------------------ income, vintage, bureau
    min_inc = float(policy.get(f"eligibility.min_monthly_income.{emp}", 25000))
    if assessed_income < min_inc:
        hits.append(hit(policy, "ELG-INC-01", OC.FAIL,
                        f"Assessed monthly income of {fmt_inr(assessed_income)} is below the minimum of {fmt_inr(min_inc)}.",
                        effect="DECLINE", severity=S.HIGH, evidence={"assessed_income": assessed_income, "min": min_inc}))
    else:
        hits.append(hit(policy, "ELG-INC-01", OC.PASS,
                        f"Assessed monthly income {fmt_inr(assessed_income)} meets the minimum of {fmt_inr(min_inc)}.",
                        evidence={"assessed_income": assessed_income, "sources": inc["sources"]}))
    min_yrs = float(policy.get(f"eligibility.min_years_in_job.{emp}", 1))
    what = "business vintage" if form.employment_type == EmploymentType.SELF_EMPLOYED else "time in current employment"
    if form.years_in_job < min_yrs:
        hits.append(hit(policy, "ELG-VIN-01", OC.WARN,
                        f"{what.capitalize()} is {form.years_in_job:.1f} years, below the {min_yrs:.0f}-year norm.",
                        effect="REFER", severity=S.MEDIUM, evidence={"years": form.years_in_job, "min": min_yrs}))
    else:
        hits.append(hit(policy, "ELG-VIN-01", OC.PASS, f"{what.capitalize()} of {form.years_in_job:.1f} years meets the norm.",
                        evidence={"years": form.years_in_job}))
    bscore = form.bureau_score
    min_b, ref_b = int(elg.get("min_bureau_score", 650)), int(elg.get("refer_bureau_score", 700))
    if bscore is None:
        hits.append(hit(policy, "ELG-BUR-01", OC.INFO,
                        "No bureau score available (new to credit); assessed on income and banking.",
                        severity=S.LOW))
    elif bscore < min_b:
        hits.append(hit(policy, "ELG-BUR-01", OC.FAIL, f"Bureau score {bscore} is below the minimum of {min_b}.",
                        effect="DECLINE", severity=S.HIGH, evidence={"bureau_score": bscore}))
    elif bscore < ref_b:
        hits.append(hit(policy, "ELG-BUR-01", OC.WARN,
                        f"Bureau score {bscore} is in the {min_b}-{ref_b - 1} band that needs underwriter review.",
                        effect="REFER", severity=S.MEDIUM, evidence={"bureau_score": bscore}))
    else:
        hits.append(hit(policy, "ELG-BUR-01", OC.PASS, f"Bureau score {bscore} is at or above {ref_b}.",
                        evidence={"bureau_score": bscore}))

    # ------------------------------------------------------------ FOIR & LTV
    foir_id, foir_cap = policy.foir_cap(assessed_income)
    requested = float(form.loan_amount)
    req_emi = emi(requested, rate, tenure)
    foir_actual = (existing + req_emi) / assessed_income if assessed_income > 0 else 9.99
    max_emi = max(0.0, foir_cap * assessed_income - existing)
    max_by_foir = principal_from_emi(max_emi, rate, tenure)

    pv, pv_parts = property_value_basis(form, bundle)
    ltv_id, ltv_cap, _ = policy.ltv_cap(form.product, requested, form.property_type)
    ltv_actual = requested / pv if pv > 0 else 9.99
    max_by_ltv, ltv_best_id, _ = policy.max_loan_by_ltv(form.product, pv, form.property_type)
    max_eligible = _cap_loan(form, policy, max_by_foir, max_by_ltv)
    min_share = float(policy.get("decision.min_reduced_share", 0.5))
    feasible = max_eligible >= min_share * requested and max_eligible > 0

    foir_ev = {"assessed_income": round(assessed_income, 2), "existing_emi": round(existing, 2),
               "proposed_emi": round(req_emi, 2), "foir": round(foir_actual, 4), "cap": foir_cap,
               "max_emi_affordable": round(max_emi, 2), "max_loan_by_foir": round(max_by_foir, 2)}
    if foir_actual <= foir_cap:
        hits.append(hit(policy, foir_id, OC.PASS,
                        f"FOIR is {pct(foir_actual)} ({fmt_inr(existing)} existing + {fmt_inr(req_emi)} proposed EMI on "
                        f"{fmt_inr(assessed_income)} income), within the {pct(foir_cap, 0)} cap.", evidence=foir_ev))
    else:
        margin = float(elg.get("foir_refer_margin", 0.05))
        hits.append(hit(policy, foir_id, OC.FAIL,
                        f"FOIR would be {pct(foir_actual)} against a cap of {pct(foir_cap, 0)}: obligations of "
                        f"{fmt_inr(existing)} plus the proposed EMI of {fmt_inr(req_emi)} on {fmt_inr(assessed_income)} income. "
                        f"Income supports at most {fmt_inr(max_by_foir)}.",
                        effect="REDUCE_AMOUNT" if feasible else "DECLINE",
                        severity=S.MEDIUM if foir_actual <= foir_cap + margin else S.HIGH, evidence=foir_ev))
    ltv_ev = {"loan": requested, "property_value": pv, "values": pv_parts, "ltv": round(ltv_actual, 4), "cap": ltv_cap,
              "max_loan_by_ltv": round(max_by_ltv, 2)}
    if ltv_actual <= ltv_cap + 1e-9:
        hits.append(hit(policy, ltv_id, OC.PASS,
                        f"LTV is {pct(ltv_actual)} ({fmt_inr(requested)} on property value {fmt_inr(pv)}), within the "
                        f"{pct(ltv_cap, 0)} cap.", evidence=ltv_ev))
    else:
        hits.append(hit(policy, ltv_id, OC.FAIL,
                        f"LTV would be {pct(ltv_actual)} ({fmt_inr(requested)} on property value {fmt_inr(pv)}) against a "
                        f"cap of {pct(ltv_cap, 0)}; the property supports at most {fmt_inr(max_by_ltv)}.",
                        effect="REDUCE_AMOUNT" if feasible else "DECLINE", severity=S.HIGH,
                        evidence={**ltv_ev, "binding_slab": ltv_best_id}))
    if form.product == Product.LAP:
        lap_max = float(policy.get("lap.max_loan", 5e7))
        if requested > lap_max:
            hits.append(hit(policy, "ELG-LAP-01", OC.FAIL,
                            f"Requested {fmt_inr(requested)} exceeds the LAP maximum of {fmt_inr(lap_max)}.",
                            effect="REDUCE_AMOUNT", severity=S.MEDIUM, evidence={"requested": requested, "max": lap_max}))

    # ------------------------------------------------------------ banking conduct
    bcfg = policy.section("banking")
    if bank.months_covered <= 0:
        hits.append(hit(policy, "BNK-STMT-01", OC.WARN, "No bank statement could be analysed.",
                        effect="CONDITION", severity=S.MEDIUM, evidence={"condition": "SUBMIT_DOC"}))
    else:
        min_m = float(bcfg.get("min_months_statement", 6))
        if bank.months_covered < min_m - 0.5:
            hits.append(hit(policy, "BNK-STMT-01", OC.WARN,
                            f"Bank statement covers {bank.months_covered} months; {min_m:.0f} months are required.",
                            effect="CONDITION", severity=S.LOW,
                            evidence={"months": bank.months_covered, "condition": "SUBMIT_DOC"}))
        else:
            hits.append(hit(policy, "BNK-STMT-01", OC.PASS, f"Bank statement covers {bank.months_covered} months.",
                            evidence={"months": bank.months_covered}))
        mx, dec = int(bcfg.get("max_bounces_6m", 2)), int(bcfg.get("decline_bounces_6m", 4))
        bev = {"bounces": bank.bounces, "details": bank.bounce_details[:6]}
        if bank.bounces >= dec:
            hits.append(hit(policy, "BNK-BNC-01", OC.FAIL,
                            f"{bank.bounces} cheque/NACH bounces in the statement period (decline at {dec} or more).",
                            effect="DECLINE", severity=S.HIGH, evidence=bev))
        elif bank.bounces > mx:
            hits.append(hit(policy, "BNK-BNC-01", OC.WARN,
                            f"{bank.bounces} cheque/NACH bounces in the statement period, above the limit of {mx}.",
                            effect="REFER", severity=S.MEDIUM, evidence=bev))
        else:
            hits.append(hit(policy, "BNK-BNC-01", OC.PASS, f"{bank.bounces} bounces, within the limit of {mx}.", evidence=bev))
        amb_mult = float(bcfg.get("min_avg_balance_to_emi", 1.0))
        if req_emi > 0 and bank.avg_monthly_balance < amb_mult * req_emi:
            hits.append(hit(policy, "BNK-AMB-01", OC.WARN,
                            f"Average monthly balance of {fmt_inr(bank.avg_monthly_balance)} is below the proposed EMI of "
                            f"{fmt_inr(req_emi)}.", effect="CONDITION", severity=S.LOW,
                            evidence={"amb": bank.avg_monthly_balance, "emi": round(req_emi, 2), "condition": "EMI_RESERVE"}))
        else:
            hits.append(hit(policy, "BNK-AMB-01", OC.PASS,
                            f"Average monthly balance of {fmt_inr(bank.avg_monthly_balance)} covers the proposed EMI.",
                            evidence={"amb": bank.avg_monthly_balance, "emi": round(req_emi, 2)}))
        if form.employment_type == EmploymentType.SALARIED:
            reg_min = float(bcfg.get("salary_regularity_min", 0.8))
            if bank.salary_regularity < reg_min:
                hits.append(hit(policy, "BNK-SAL-01", OC.WARN,
                                f"Salary credits are irregular (regularity {bank.salary_regularity:.2f} vs {reg_min:.2f} "
                                f"required); salary-account statement needed.", effect="CONDITION", severity=S.MEDIUM,
                                evidence={"regularity": bank.salary_regularity, "condition": "SUBMIT_DOC",
                                          "salary_credits": bank.salary_credits}))
            else:
                hits.append(hit(policy, "BNK-SAL-01", OC.PASS,
                                f"Salary credited regularly (regularity {bank.salary_regularity:.2f}), average "
                                f"{fmt_inr(bank.avg_salary_credit)}.", evidence={"regularity": bank.salary_regularity}))

    # ------------------------------------------------------------ tenure options
    options: list[TenureOption] = []
    grid = sorted({int(t) for t in policy.get("decision.tenure_options", [120, 180, 240, 300, 360])} | {tenure_cap})
    for t in grid:
        if t < min_tenure or t > tenure_cap:
            continue
        e = emi(requested, rate, t)
        options.append(TenureOption(
            tenure_months=t,
            max_loan=round(_cap_loan(form, policy, principal_from_emi(max_emi, rate, t), max_by_ltv), 2),
            emi_for_requested=round(e, 2),
            foir_at_requested=round((existing + e) / assessed_income, 4) if assessed_income > 0 else 9.99,
        ))

    hard_fail = any(h.effect == "DECLINE" for h in hits)
    eligible = (not hard_fail) and requested <= max_eligible + 1
    notes.append(f"Income basis: {basis}.")
    if dob:
        notes.append(f"Age {age:.1f}; loan matures at {age_at_maturity:.1f} (limit {max_age_mat:.0f}).")

    result = Eligibility(
        policy_version=policy.version,
        assessed_income=round(assessed_income, 2),
        income_basis=basis,
        existing_obligations=round(existing, 2),
        foir_cap=foir_cap,
        foir_actual=round(foir_actual, 4),
        ltv_cap=ltv_cap,
        ltv_actual=round(ltv_actual, 4),
        ltv_rule_id=ltv_id,
        rate=rate,
        max_tenure_months=tenure_cap,
        age_at_maturity=age_at_maturity,
        max_emi_affordable=round(max_emi, 2),
        max_loan_by_foir=round(max_by_foir, 2),
        max_loan_by_ltv=round(max_by_ltv, 2),
        max_eligible_loan=round(max_eligible, 2),
        requested_amount=requested,
        requested_emi=round(req_emi, 2),
        eligible=eligible,
        tenure_options=options,
        notes=notes,
        tenure_months=tenure,
        property_value=round(pv, 2),
    )
    return result, hits
