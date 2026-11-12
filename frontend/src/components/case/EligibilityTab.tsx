import type { CaseDetail, RuleHit } from "@/lib/types";
import { inr, months, pct, rate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { findRule } from "@/lib/rules";
import { Card, CardHeader } from "@/components/ui/Card";
import { RuleOutcomeChip } from "@/components/ui/Badges";
import { Bar, Disclaimer, Label, RuleId } from "@/components/ui/misc";

function CheckTile({
  name,
  actual,
  limit,
  fill,
  rule,
  basis,
}: {
  name: string;
  actual: string;
  limit: string;
  fill: number;
  rule?: RuleHit;
  basis: string;
}) {
  const tone = rule?.outcome === "FAIL" ? "bad" : rule?.outcome === "WARN" ? "auto" : "olive";
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-surface border border-hairline bg-paper p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">{name}</p>
          {rule && <RuleId id={rule.rule_id} className="mt-1" />}
        </div>
        {rule && <RuleOutcomeChip outcome={rule.outcome} />}
      </div>
      <p className="font-display text-2xl font-semibold text-ink tnum">
        {actual} <span className="text-sm font-normal text-pewter">vs {limit}</span>
      </p>
      <Bar value={Math.min(100, fill * 100)} tone={tone === "auto" ? "auto" : tone} className={cn(tone === "auto" && "[&>div]:bg-warn-solid")} />
      <p className="text-xs text-graphite">{rule?.detail ?? basis}</p>
      {rule?.reference && (
        <p className="truncate text-[11px] text-pewter" title={rule.reference}>
          {rule.reference}
        </p>
      )}
    </div>
  );
}

export function EligibilityTab({ c }: { c: CaseDetail }) {
  const e = c.eligibility;
  const maxAge = c.form.employment_type === "SALARIED" ? 60 : 70;
  const tenure = e.tenure_months || c.form.tenure_months;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CheckTile
          name="FOIR"
          actual={pct(e.foir_actual)}
          limit={`${pct(e.foir_cap)} cap`}
          fill={e.foir_cap ? e.foir_actual / e.foir_cap : 0}
          rule={findRule(c, (id) => id.startsWith("ELG-FOIR"))}
          basis="(existing EMIs + proposed EMI) ÷ assessed income"
        />
        <CheckTile
          name="Loan to value"
          actual={pct(e.ltv_actual)}
          limit={`${pct(e.ltv_cap)} cap`}
          fill={e.ltv_cap ? e.ltv_actual / e.ltv_cap : 0}
          rule={findRule(c, (id) => id === e.ltv_rule_id) ?? findRule(c, (id) => id.startsWith("LTV"))}
          basis={`Loan ÷ lower of agreement value and valuation (${inr(e.property_value || c.form.property_value)})`}
        />
        <CheckTile
          name="Age at maturity"
          actual={`${e.age_at_maturity.toFixed(1)} yrs`}
          limit={`${maxAge} yrs`}
          fill={e.age_at_maturity / maxAge}
          rule={findRule(c, (id) => id.startsWith("ELG-AGE-02") || id.startsWith("ELG-MAT"))}
          basis={`Applicant age ${c.applicant.age.toFixed(1)} + tenure`}
        />
        <CheckTile
          name="Tenure"
          actual={`${tenure} mo`}
          limit={`${e.max_tenure_months} mo max`}
          fill={e.max_tenure_months ? tenure / e.max_tenure_months : 0}
          rule={findRule(c, (id) => id.startsWith("ELG-TEN"))}
          basis="Product limit and age-at-maturity limit"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-5">
          <CardHeader title="How the amount was sized" subtitle="Every number traces to the policy and the documents" />
          <dl className="divide-y divide-hairline text-sm">
            {[
              ["Assessed income / month", inr(e.assessed_income)],
              ["Existing obligations / month", inr(e.existing_obligations)],
              ["Rate applied", rate(e.rate)],
              ["Max EMI within FOIR", inr(e.max_emi_affordable)],
              ["Max loan by FOIR", inr(e.max_loan_by_foir)],
              ["Max loan by LTV", inr(e.max_loan_by_ltv)],
              ["Requested", `${inr(e.requested_amount)} · EMI ${inr(e.requested_emi)}`],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3 py-2">
                <dt className="text-graphite">{k}</dt>
                <dd className="text-right font-semibold text-ink tnum">{v}</dd>
              </div>
            ))}
            <div className="flex items-center justify-between gap-3 py-3">
              <dt className="font-semibold text-ink">Max eligible loan</dt>
              <dd className="font-display text-2xl font-semibold text-ink tnum">{inr(e.max_eligible_loan)}</dd>
            </div>
          </dl>
          <div className="mt-2 rounded-surface bg-sage p-3 text-xs text-ink">
            <Label className="block">Income basis</Label>
            <p className="mt-1">{e.income_basis}</p>
          </div>
          {e.notes.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-graphite">
              {e.notes.map((n, i) => (
                <li key={i}>• {n}</li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="lg:col-span-7">
          <CardHeader title="Tenure options" subtitle="What the same income supports at different tenures" />
          <div className="-mx-4 overflow-x-auto sm:-mx-5">
            <table className="w-full min-w-[520px] text-[13px]">
              <thead>
                <tr className="text-left text-xs text-graphite">
                  <th className="px-5 py-2 font-medium">Tenure</th>
                  <th className="px-3 py-2 text-right font-medium">Max loan</th>
                  <th className="px-3 py-2 text-right font-medium">EMI for requested</th>
                  <th className="px-5 py-2 text-right font-medium">FOIR at requested</th>
                </tr>
              </thead>
              <tbody>
                {e.tenure_options.map((t) => {
                  const ok = t.foir_at_requested <= e.foir_cap;
                  const current = t.tenure_months === tenure;
                  return (
                    <tr key={t.tenure_months} className={cn("border-t border-hairline", current && "bg-tint-lime")}>
                      <td className="px-5 py-2.5 font-medium text-ink">
                        {months(t.tenure_months)} {current && <span className="ml-1 text-[11px] text-olive">requested</span>}
                      </td>
                      <td className="px-3 py-2.5 text-right font-semibold text-ink tnum">{inr(t.max_loan)}</td>
                      <td className="px-3 py-2.5 text-right text-graphite tnum">{inr(t.emi_for_requested)}</td>
                      <td className={cn("px-5 py-2.5 text-right font-semibold tnum", ok ? "text-ok" : "text-bad")}>
                        {pct(t.foir_at_requested)} {ok ? "✓" : "✕"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-pewter">FOIR cap {pct(e.foir_cap)} · ✓ within cap, ✕ above cap. Tenures beyond {e.max_tenure_months} months are not allowed for this applicant.</p>
        </Card>
      </div>
      <Disclaimer text={c.disclaimer} />
    </div>
  );
}
