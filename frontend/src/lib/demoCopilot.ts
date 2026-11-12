/**
 * Offline Copilot: a small grounded responder that answers only from the case
 * file and cites rule IDs. Used when the backend is unreachable (demo mode).
 */
import type { CaseDetail, Citation, CopilotAnswer, RuleHit } from "./types";
import { inr, pct, rate } from "./format";
import { OUTCOME_LABEL } from "./labels";

function emi(principal: number, annualRate: number, n: number): number {
  const r = annualRate / 12;
  if (r === 0) return principal / n;
  return (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1);
}

function ruleCite(r: RuleHit): Citation {
  return { kind: "rule", ref: r.rule_id, text: r.detail };
}

function nonPass(c: CaseDetail): RuleHit[] {
  const seen = new Set<string>();
  return c.decision.rules_fired
    .filter((r) => r.outcome === "FAIL" || r.outcome === "WARN")
    .sort((x, y) => (x.outcome === y.outcome ? 0 : x.outcome === "FAIL" ? -1 : 1))
    .filter((r) => (seen.has(r.rule_id) ? false : (seen.add(r.rule_id), true)));
}

function answer(text: string, citations: Citation[]): CopilotAnswer {
  return { answer: text, citations: citations.slice(0, 8), engine: "offline-grounded (demo)", grounded: true };
}

export function answerOffline(c: CaseDetail, question: string): CopilotAnswer {
  const q = question.toLowerCase();
  const d = c.decision;
  const e = c.eligibility;
  const issues = nonPass(c);

  const tenureMatch = /(\d{2,3})\s*(months|month|mo)\b/.exec(q) ?? /(\d{1,2})\s*(years|year|yrs|yr)\b/.exec(q);
  if (q.includes("tenure") || tenureMatch) {
    const n = tenureMatch ? Number(tenureMatch[1]) * (tenureMatch[2].startsWith("y") ? 12 : 1) : e.max_tenure_months;
    const capped = Math.min(n, e.max_tenure_months);
    const amount = d.sanctioned_amount || e.requested_amount;
    const r = d.rate || e.rate;
    const newEmi = emi(e.requested_amount, r, capped);
    const foir = e.assessed_income > 0 ? (e.existing_obligations + newEmi) / e.assessed_income : 0;
    const foirRule = d.rules_fired.find((x) => x.rule_id.startsWith("ELG-FOIR"));
    const tenureRule = d.rules_fired.find((x) => x.rule_id.startsWith("ELG-TEN"));
    const note = n > e.max_tenure_months ? ` ${n} months exceeds the maximum of ${e.max_tenure_months} months (age at maturity / product limit), so I used ${capped}.` : "";
    return answer(
      `At ${capped} months and ${rate(r)}, the requested ${inr(e.requested_amount)} would have an EMI of about ${inr(newEmi)}. ` +
        `With existing obligations of ${inr(e.existing_obligations)} on assessed income of ${inr(e.assessed_income)}, FOIR would be ${pct(foir)} against a cap of ${pct(e.foir_cap)} — ` +
        `${foir <= e.foir_cap ? "within policy" : "still above the cap"}.${note} The current sanction is ${inr(amount)} over ${d.tenure_months} months.`,
      [foirRule, tenureRule].filter((x): x is RuleHit => Boolean(x)).map(ruleCite),
    );
  }

  if (/(document|missing|doc\b|docs|kyc)/.test(q)) {
    const missing = c.bundle.missing_documents;
    const flags = c.bundle.flags;
    const docRules = d.rules_fired.filter((r) => ["DOCUMENT", "KYC"].includes(r.category) && r.outcome !== "PASS");
    const text =
      (missing.length ? `Missing documents: ${missing.join(", ")}. ` : "All required documents are present. ") +
      (flags.length ? `${flags.length} document flag(s): ${flags.map((f) => f.title).join("; ")}.` : "No document tampering flags were raised.");
    return answer(text, [
      ...docRules.map(ruleCite),
      ...c.bundle.documents.slice(0, 3).map((doc) => ({ kind: "document" as const, ref: doc.id, text: `${doc.doc_type} · ${doc.filename}` })),
    ]);
  }

  if (/(fraud|tamper|forg|suspicious|negative|pep|sanction list)/.test(q)) {
    const fr = d.rules_fired.filter((r) => r.category === "FRAUD" || r.category === "COMPLIANCE").filter((r) => r.outcome !== "PASS");
    return answer(
      fr.length
        ? `${fr.length} fraud/compliance check(s) need attention: ${fr.map((r) => `${r.rule_id} (${r.outcome}): ${r.detail}`).join(" ")}`
        : "All fraud and compliance checks passed for this case.",
      fr.map(ruleCite),
    );
  }

  if (/(foir|obligation|income)/.test(q)) {
    const r = d.rules_fired.filter((x) => x.rule_id.startsWith("ELG-FOIR") || x.rule_id.startsWith("ELG-INC"));
    return answer(
      `Assessed income is ${inr(e.assessed_income)} a month (${e.income_basis}). Existing obligations are ${inr(e.existing_obligations)}; with the proposed EMI of ${inr(e.requested_emi)} FOIR is ${pct(e.foir_actual)} vs a cap of ${pct(e.foir_cap)}. ` +
        `The maximum loan the FOIR cap allows is ${inr(e.max_loan_by_foir)}.`,
      r.map(ruleCite),
    );
  }

  if (/(ltv|property|valuation)/.test(q)) {
    const r = d.rules_fired.filter((x) => x.rule_id === e.ltv_rule_id || x.rule_id.startsWith("LTV") || x.rule_id.startsWith("CMP-VAL"));
    return answer(
      `LTV is ${pct(e.ltv_actual)} on a property value of ${inr(e.property_value || c.form.property_value)} against the ${pct(e.ltv_cap)} cap under ${e.ltv_rule_id}. The LTV cap allows up to ${inr(e.max_loan_by_ltv)}.`,
      r.map(ruleCite),
    );
  }

  if (/(shap|model|pd\b|probability|score|grade|risk)/.test(q)) {
    const top = c.risk.reasons.slice(0, 4);
    return answer(
      `The model estimates a PD of ${pct(c.risk.pd, 2)} (score ${c.risk.score}, grade ${c.risk.grade}, ${c.risk.band}). Main drivers: ${top.map((t) => t.text).join("; ")}. ` +
        `On its own the model would suggest ${OUTCOME_LABEL[d.model_suggested]}; policy rules take precedence.`,
      [
        ...top.map((t) => ({ kind: "metric" as const, ref: t.feature, text: t.text })),
        ...d.rules_fired.filter((r) => r.rule_id.startsWith("RSK")).map(ruleCite),
      ],
    );
  }

  if (/(condition|approv|path|what would|how can|get to)/.test(q)) {
    return answer(
      d.conditions.length
        ? `To proceed: ${d.conditions.map((x, i) => `${i + 1}. ${x.text}`).join(" ")}`
        : `No conditions are attached. The case is ${OUTCOME_LABEL[d.outcome]}.`,
      issues.map(ruleCite),
    );
  }

  if (/(rule|fail|warn|check)/.test(q)) {
    return answer(
      issues.length
        ? `${issues.length} rule(s) did not pass: ${issues.map((r) => `${r.rule_id} ${r.name} (${r.outcome})`).join("; ")}.`
        : "Every rule passed.",
      issues.map(ruleCite),
    );
  }

  // Default: explain the decision.
  return answer(
    `This case is ${OUTCOME_LABEL[d.outcome]}${d.sanctioned_amount ? ` for ${inr(d.sanctioned_amount)} over ${d.tenure_months} months at ${rate(d.rate)}` : ""}. ` +
      d.reasons.join(" ") +
      (issues.length ? ` Rules that drove it: ${issues.slice(0, 5).map((r) => r.rule_id).join(", ")}.` : ""),
    issues.map(ruleCite),
  );
}
