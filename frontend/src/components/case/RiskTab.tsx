import { Bar, BarChart, Cell, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pct } from "@/lib/format";
import { OUTCOME_LABEL } from "@/lib/labels";
import { chartColors, useTheme } from "@/lib/theme";
import type { CaseDetail, ShapReason } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { GradeChip } from "@/components/ui/Badges";
import { Gauge } from "@/components/ui/Gauge";
import { Label } from "@/components/ui/misc";
import { Legend, TooltipBox } from "@/components/charts/ChartTooltip";

function display(v: ShapReason["value"]): string {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return v == null ? "—" : String(v);
}

function ShapChart({ reasons }: { reasons: ShapReason[] }) {
  const [theme] = useTheme();
  const k = chartColors(theme);
  const data = [...reasons]
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, 10)
    .map((r) => ({ label: r.label, impact: r.impact, value: display(r.value), text: r.text }));
  const max = Math.max(0.1, ...data.map((d) => Math.abs(d.impact)));
  return (
    <div style={{ height: Math.max(220, data.length * 40 + 40) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 16, top: 4, bottom: 4 }} barSize={18}>
          <CartesianGrid horizontal={false} stroke={k.grid} />
          <XAxis type="number" domain={[-max * 1.1, max * 1.1]} tickFormatter={(v: number) => v.toFixed(1)} tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={200}
            tick={{ fill: k.ink, fontSize: 12 }}
            tickFormatter={(v: string) => (v.length > 30 ? `${v.slice(0, 29)}…` : v)}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceLine x={0} stroke={k.axis} />
          <Tooltip
            cursor={{ fill: k.grid }}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
              if (!p) return null;
              return (
                <TooltipBox
                  title={p.label}
                  rows={[
                    { label: "Value", value: p.value },
                    { label: "SHAP (log-odds)", value: `${p.impact > 0 ? "+" : ""}${p.impact.toFixed(3)}`, color: p.impact > 0 ? k.rose : k.emerald },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="impact" radius={4} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.label} fill={d.impact > 0 ? k.rose : k.emerald} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskTab({ c }: { c: CaseDetail }) {
  const r = c.risk;
  const [theme] = useTheme();
  const k = chartColors(theme);
  const sorted = [...r.reasons].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardHeader
            title="What moved the risk estimate"
            subtitle="SHAP contributions (log-odds) for this applicant. Right = increases default risk, left = reduces it."
            action={<Legend items={[{ label: "Increases risk", color: k.rose }, { label: "Reduces risk", color: k.emerald }]} />}
          />
          <ShapChart reasons={r.reasons} />
        </Card>
        <Card className="flex flex-col items-center gap-3 lg:col-span-4">
          <div className="w-full">
            <CardHeader title="Risk score" subtitle="Calibrated PD mapped to a 300–900 scale" className="mb-2" />
          </div>
          <div className="rounded-[24px] bg-sage p-3">
            <Gauge value={r.score - 300} max={600} display={r.score} label="Risk score" caption="of 900 (300–900 scale)" size={170} />
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <GradeChip grade={r.grade} band={r.band} />
            <Chip tone="outline">PD {pct(r.pd, 2)}</Chip>
          </div>
          <Chip tone="neutral" className="font-mono text-[11px]">
            {r.model_version}
          </Chip>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="In plain language" subtitle="Top drivers, strongest first" />
          <ol className="space-y-2">
            {sorted.map((s, i) => (
              <li key={s.feature} className="flex items-start gap-3 rounded-surface bg-fog px-3 py-2.5">
                <span className="mt-0.5 w-4 text-xs text-pewter tnum">{i + 1}</span>
                <span className="flex-1 text-sm text-ink">{s.text}</span>
                <Chip tone={s.impact > 0 ? "danger" : "success"} className="text-[11px]">
                  {s.impact > 0 ? "↑ risk" : "↓ risk"}
                </Chip>
              </li>
            ))}
          </ol>
        </Card>
        <Card className="bg-sage">
          <CardHeader title="Rules + ML hybrid" subtitle="Why the model never has the last word" />
          <div className="space-y-3 text-sm text-ink">
            <p>
              The model on its own would suggest <strong>{OUTCOME_LABEL[c.decision.model_suggested]}</strong>. The engine's decision is{" "}
              <strong>{OUTCOME_LABEL[c.decision.engine_outcome]}</strong>.
            </p>
            <p className="text-graphite">
              Hard policy rules (FOIR, LTV, KYC, fraud, end-use) are evaluated first and dominate. The PD model only sets the risk grade and price, and can
              tighten a decision (refer or add conditions) but never relax a rule failure.
            </p>
            <div className="rounded-surface bg-paper p-3">
              <Label className="block">Model</Label>
              <p className="mt-1 text-xs text-graphite">
                LightGBM with monotone constraints, Platt-calibrated, explained with SHAP TreeExplainer. Base log-odds {r.base_value.toFixed(2)}.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
