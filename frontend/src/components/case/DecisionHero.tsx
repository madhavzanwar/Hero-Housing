import { Gavel, Landmark, ShieldQuestion } from "lucide-react";
import type { CaseDetail, DecisionOutcome } from "@/lib/types";
import { inr, ms, pct, rate } from "@/lib/format";
import { OUTCOME_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { KpiCard, type KpiVariant } from "@/components/ui/KpiCard";
import { GradeChip } from "@/components/ui/Badges";
import { Gauge } from "@/components/ui/Gauge";

const VARIANT: Record<DecisionOutcome, KpiVariant> = {
  APPROVE: "lime",
  APPROVE_WITH_CONDITIONS: "sage",
  REFER: "info",
  DECLINE: "danger",
};

function binding(c: CaseDetail): string {
  const e = c.eligibility;
  if (e.max_eligible_loan >= e.requested_amount) return "Requested amount fits FOIR and LTV";
  return e.max_loan_by_foir <= e.max_loan_by_ltv ? `Limited by FOIR (${pct(e.foir_cap)} cap)` : `Limited by LTV (${pct(e.ltv_cap)} cap, ${e.ltv_rule_id})`;
}

export function DecisionHero({ c }: { c: CaseDetail }) {
  const d = c.decision;
  const e = c.eligibility;
  const approved = d.outcome === "APPROVE" || d.outcome === "APPROVE_WITH_CONDITIONS";
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="Decision"
        icon={Gavel}
        variant={VARIANT[d.outcome]}
        value={<span className={cn("block text-2xl leading-tight", d.outcome === "DECLINE" && "text-bad", d.outcome === "REFER" && "text-info")}>{OUTCOME_LABEL[d.outcome]}</span>}
        sub={
          approved || d.sanctioned_amount > 0 ? (
            <>
              <span className="font-semibold tnum">{inr(d.sanctioned_amount)}</span> · EMI {inr(d.emi)} × {d.tenure_months} mo @ {rate(d.rate)}
            </>
          ) : (
            "No sanction — reasons below"
          )
        }
        footer={
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span data-testid="decision-outcome" className="rounded-md bg-paper/70 px-1.5 py-0.5 font-mono font-semibold text-[#0d0d0d] dark:text-ink">
              {d.outcome}
            </span>
            <span className="opacity-75">
              {d.decided_by === "engine" ? `Engine · ${ms(d.turnaround_ms)}` : `By ${d.decided_by}`}
            </span>
          </div>
        }
      />
      <KpiCard
        label="Max eligible loan"
        icon={Landmark}
        value={inr(e.max_eligible_loan)}
        sub={
          <>
            {binding(c)}
            <br />
            Requested {inr(e.requested_amount)}
          </>
        }
      />
      <KpiCard
        label="Probability of default"
        icon={ShieldQuestion}
        value={pct(c.risk.pd, 2)}
        sub={
          <span className="flex flex-wrap items-center gap-2">
            <GradeChip grade={c.risk.grade} band={c.risk.band} />
            <span>Score {c.risk.score} / 900</span>
          </span>
        }
      />
      <div className="relative flex min-w-0 flex-col overflow-hidden rounded-card bg-surface p-5 elevation-card">
        <span className="text-sm font-medium text-graphite">Repayment health</span>
        <div className="mt-1 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-display text-[28px] font-semibold leading-tight text-ink tnum">{pct(c.capacity.prob_shortfall, 0)}</p>
            <p className="text-xs text-graphite">P(shortfall) after EMI</p>
          </div>
          <div className="shrink-0 rounded-[20px] bg-sage p-1">
            <Gauge value={c.capacity.health_score} label="Repayment health score" caption="/ 100" size={88} />
          </div>
        </div>
        <p className="mt-auto pt-2 text-xs text-graphite">{c.capacity.iterations.toLocaleString("en-IN")} Monte Carlo paths · health {Math.round(c.capacity.health_score)}/100</p>
      </div>
    </div>
  );
}
