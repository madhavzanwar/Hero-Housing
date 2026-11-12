import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { inr, inrShort, pct } from "@/lib/format";
import { chartColors, useTheme } from "@/lib/theme";
import type { CaseDetail, RepaymentCapacity } from "@/lib/types";
import { cn, num } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { Gauge } from "@/components/ui/Gauge";
import { Bar, Disclaimer, Label } from "@/components/ui/misc";
import { StatTile } from "@/components/ui/StatTile";
import { Legend, TooltipBox } from "@/components/charts/ChartTooltip";

function tier(score: number): { text: string; tone: "success" | "warning" | "danger" } {
  if (score >= 75) return { text: "Comfortable", tone: "success" };
  if (score >= 55) return { text: "Moderate", tone: "warning" };
  return { text: "Needs attention", tone: "danger" };
}

function HealthIndex({ cap }: { cap: RepaymentCapacity }) {
  const t = tier(cap.health_score);
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            Repayment health index <Chip tone={t.tone}>{t.text}</Chip>
          </span>
        }
        subtitle="FinPilot weighted 5-pillar model, re-based on the proposed EMI"
      />
      <div className="grid grid-cols-1 items-center gap-5 lg:grid-cols-12">
        <div className="flex flex-col items-center justify-center rounded-3xl bg-sage p-5 lg:col-span-4">
          <Gauge value={cap.health_score} label="Repayment health" caption="out of 100" size={160} />
        </div>
        <div className="grid grid-cols-1 gap-2 lg:col-span-8 xl:grid-cols-2">
          {cap.sub_scores.map((s) => (
            <div key={s.name} className="flex flex-col gap-1.5 rounded-chip border border-hairline bg-paper px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-semibold text-ink">{s.name}</span>
                  <span className="shrink-0 rounded border border-hairline bg-fog px-1.5 py-0.5 text-[10px] font-medium text-pewter">Weight {Math.round(s.weight * 100)}%</span>
                </div>
                <span className="shrink-0 text-sm font-bold text-ink tnum">
                  {Math.round(s.score)}
                  <span className="text-[11px] font-normal text-pewter"> /100</span>
                </span>
              </div>
              <Bar value={s.score} />
              <span className="line-clamp-2 text-[11px] text-graphite">{s.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function FanChart({ cap }: { cap: RepaymentCapacity }) {
  const [theme] = useTheme();
  const k = chartColors(theme);
  const data = cap.forecast.map((p) => ({ month: `M${p.month}`, base: p.p10, band: p.p90 - p.p10, p10: p.p10, p50: p.p50, p90: p.p90 }));
  return (
    <Card className="lg:col-span-8">
      <CardHeader
        title="Bank buffer after EMI"
        subtitle={`Median path and 80% interval (P10–P90) over ${cap.forecast.length} months · ${cap.iterations.toLocaleString("en-IN")} Monte Carlo paths`}
        action={
          <Legend
            items={[
              { label: "Median (P50)", color: k.olive },
              { label: "P10–P90", color: k.sage },
              { label: "Zero buffer", color: k.rose, dashed: true },
            ]}
          />
        }
      />
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={k.grid} />
            <XAxis dataKey="month" tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={18} />
            <YAxis tickFormatter={(v: number) => inrShort(v)} tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
            <Tooltip
              content={({ payload, label }) => {
                const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!p) return null;
                return (
                  <TooltipBox
                    title={label}
                    rows={[
                      { label: "P90", value: inr(p.p90) },
                      { label: "P50", value: inr(p.p50), color: k.olive },
                      { label: "P10", value: inr(p.p10) },
                    ]}
                  />
                );
              }}
            />
            <Area dataKey="base" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area dataKey="band" stackId="band" stroke="none" fill={k.sage} fillOpacity={0.75} isAnimationActive={false} />
            <ReferenceLine y={0} stroke={k.rose} strokeDasharray="5 4" label={{ value: "Zero", position: "insideBottomRight", fill: k.rose, fontSize: 11 }} />
            <Line dataKey="p50" stroke={k.olive} strokeWidth={2.25} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-pewter">Solid = median; shaded = 80% prediction interval. Bootstrapped from the applicant's own monthly net cash flow.</p>
    </Card>
  );
}

export function CapacityTab({ c }: { c: CaseDetail }) {
  const cap = c.capacity;
  const stressOk = cap.stress_emi_coverage >= 1;
  return (
    <div className="space-y-4">
      <HealthIndex cap={cap} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <FanChart cap={cap} />
        <div className="flex flex-col gap-3 lg:col-span-4">
          <StatTile
            label="Surplus after EMI"
            value={inr(cap.monthly_surplus_after_emi)}
            sub="median monthly, after the proposed EMI"
            status={cap.monthly_surplus_after_emi >= 0 ? { tone: "success", text: "Positive" } : { tone: "danger", text: "Negative" }}
          />
          <StatTile
            label="P(shortfall)"
            value={pct(cap.prob_shortfall, 0)}
            sub="buffer below zero in any month"
            status={cap.prob_shortfall <= 0.2 ? { tone: "success", text: "Low" } : cap.prob_shortfall <= 0.4 ? { tone: "warning", text: "Watch" } : { tone: "danger", text: "High" }}
          />
          <div className={cn("rounded-[20px] p-4", stressOk ? "bg-sage" : "bg-bad-soft")}>
            <Label className="block">Stress test</Label>
            <p className="mt-1 font-display text-2xl font-semibold text-ink tnum">{num(cap.stress_emi_coverage)?.toFixed(2) ?? "—"}× coverage</p>
            <p className="mt-1 text-xs text-graphite">Surplus ÷ EMI after a +200 bps rate shock and −15% income. Policy wants at least 1.0×.</p>
            <Chip tone={stressOk ? "success" : "danger"} className="mt-2">
              {stressOk ? "Passes stress" : "Fails stress"}
            </Chip>
          </div>
        </div>
      </div>
      {cap.basis && <p className="text-xs text-pewter">Basis: {cap.basis}</p>}
      <Disclaimer text={c.disclaimer} />
    </div>
  );
}
