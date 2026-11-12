import type { CaseDetail, RuleHit } from "./types";

/** Most severe rule hit whose id passes `test` (FAIL > WARN > first). */
export function findRule(c: CaseDetail, test: (id: string) => boolean): RuleHit | undefined {
  const hits = c.decision.rules_fired.filter((r) => test(r.rule_id));
  return hits.find((r) => r.outcome === "FAIL") ?? hits.find((r) => r.outcome === "WARN") ?? hits[0];
}
