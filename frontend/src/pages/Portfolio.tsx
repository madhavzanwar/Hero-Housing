import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { inr, inrShort, ms, pct } from "@/lib/format";
import { OUTCOME_LABEL } from "@/lib/labels";
import { chartColors, useTheme } from "@/lib/theme";
import { DECISION_OUTCOMES } from "@/lib/types";
import { humanize } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/EmptyState";
import { Disclaimer, Label, PageHeader, RuleId } from "@/components/ui/misc";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { StatTile } from "@/components/ui/StatTile";
import { Donut } from "@/components/charts/Donut";
import { TooltipBox } from "@/components/charts/ChartTooltip";
import { outcomeColor } from "@/components/charts/outcomeColors";

/** Manual-underwriting baseline used for the TAT comparison (industry: ~3–7 working days). */
const MANUAL_TAT_HOURS = 72;

function HeroTile({ cls, label, value, sub }: { cls: string; label: string; value: string; sub: string }) {
  return (
    <div className={`${cls} relative overflow-hidden rounded-card border border-hairline p-6`}>
      <Label>{label}</Label>
      <p className="mt-3 font-display text-4xl font-semibold text-ink tnum sm:text-[44px]">{value}</p>
      <p className="mt-1 text-sm text-graphite">{sub}</p>
    </div>
  );
}

export default function Portfolio() {
  const [theme] = useTheme();
  const k = chartColors(theme);
  const res = useAsync(() => api.portfolio(), "portfolio");
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <PageSkeleton />;
  const p = res.data;
  const grades = ["A", "B", "C", "D", "E"].map((g) => ({ grade: g, n: p.grade_distribution[g] ?? 0 }));
  const maxRule = Math.max(1, ...p.top_rules.map((r) => r.count));

  return (
    <div className="space-y-4">
      <PageHeader title="Portfolio" subtitle="How the engine is deciding across every case on file: outcomes, risk mix, speed and the rules that bite most." />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <HeroTile cls="gradient-tile-1" label="Sanctioned value" value={inrShort(p.sanctioned_value)} sub={`${inr(p.sanctioned_value)} across approved cases`} />
        <HeroTile cls="gradient-tile-2" label="Approval rate" value={pct(p.approval_rate, 0)} sub={`incl. with-conditions · ${p.total_cases} cases`} />
        <HeroTile
          cls="gradient-tile-3"
          label="Average turnaround"
          value={ms(p.avg_turnaround_ms)}
          sub={`vs ~${MANUAL_TAT_HOURS} h manual baseline · ${Math.round((MANUAL_TAT_HOURS * 3600 * 1000) / Math.max(1, p.avg_turnaround_ms)).toLocaleString("en-IN")}× faster`}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Cases" value={p.total_cases} sub="on file" />
        <StatTile label="Average PD" value={pct(p.avg_pd, 2)} sub="calibrated, 12-month" />
        <StatTile label="Fraud flagged" value={p.fraud_flagged} sub="high-severity signals" status={p.fraud_flagged ? { tone: "danger", text: "Review" } : undefined} />
        <StatTile label="Override rate" value={pct(p.override_rate, 0)} sub="human changed the engine" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-5">
          <CardHeader title="Outcome mix" subtitle="Final outcome after any override" />
          <Donut
            centerLabel="Cases"
            centerValue={String(p.total_cases)}
            data={DECISION_OUTCOMES.map((o) => ({ key: o, label: OUTCOME_LABEL[o], value: p.by_outcome[o] ?? 0, color: outcomeColor(o, theme) }))}
          />
        </Card>
        <Card className="lg:col-span-4">
          <CardHeader title="Risk grade distribution" subtitle="Grades from the calibrated PD bands" />
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={grades} margin={{ left: -16, right: 4, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={k.grid} />
                <XAxis dataKey="grade" tick={{ fill: k.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: k.grid }} content={({ payload }) => (payload?.[0] ? <TooltipBox rows={[{ label: `Grade ${String(payload[0].payload.grade)}`, value: `${String(payload[0].value)} cases`, color: k.olive }]} /> : null)} />
                <Bar dataKey="n" fill={k.olive} radius={[6, 6, 0, 0]} maxBarSize={44} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title="Product mix" subtitle="Applications by product" />
          <ul className="space-y-3">
            {Object.entries(p.by_product).map(([prod, n]) => (
              <li key={prod}>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-graphite">{prod === "LAP" ? "Loan against property" : "Home loan"}</span>
                  <span className="font-semibold text-ink tnum">{n}</span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-fog">
                  <div className="h-full rounded-full" style={{ width: `${(n / Math.max(1, p.total_cases)) * 100}%`, background: prod === "LAP" ? k.cyan : k.olive }} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Rules that bite most" subtitle="Fail + warn counts across the portfolio — where applicants most often fall short of policy" />
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {p.top_rules.map((r) => (
            <li key={r.rule_id} className="rounded-surface bg-fog p-3">
              <div className="flex items-center gap-2">
                <RuleId id={r.rule_id} />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{r.name}</span>
                <span className="font-display text-lg font-semibold text-ink tnum">{r.count}</span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Chip tone="outline" className="text-[10px]">
                  {humanize(r.category)}
                </Chip>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper">
                  <div className="h-full rounded-full bg-ember" style={{ width: `${(r.count / maxRule) * 100}%` }} />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <Disclaimer />
    </div>
  );
}
