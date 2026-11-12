import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { pct } from "@/lib/format";
import { chartColors, useTheme } from "@/lib/theme";
import type { Json, JsonObject } from "@/lib/types";
import { isRecord, num, str } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/EmptyState";
import { Disclaimer, Label, PageHeader } from "@/components/ui/misc";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { StatTile } from "@/components/ui/StatTile";
import { Legend, TooltipBox } from "@/components/charts/ChartTooltip";

function obj(v: Json | undefined): JsonObject {
  return isRecord(v) ? (v as JsonObject) : {};
}
function arr(v: Json | undefined): JsonObject[] {
  return Array.isArray(v) ? (v.filter((x) => isRecord(x)) as JsonObject[]) : [];
}

const LIMITATIONS = [
  "Trained on a documented synthetic Indian mortgage dataset; performance on real bureau and bank data must be re-validated before use.",
  "Benchmarked on public UCI Taiwan and German Credit datasets only to sanity-check the method, not the Indian population.",
  "Monotone constraints keep directions sensible (more FOIR → more risk) but cannot capture every interaction.",
  "The model never overrides hard policy rules; it sets grade and price and can only tighten a decision.",
  "Fairness is measured on gender and age band in synthetic data; protected attributes are not model inputs.",
];

export default function ModelCard() {
  const [theme] = useTheme();
  const k = chartColors(theme);
  const res = useAsync(() => api.modelCard(), "model-card");
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <PageSkeleton />;
  const card = res.data;
  const m = obj(card.metrics);
  const test = obj(m.test);
  const cal = arr(obj(m.calibration).deciles).map((d) => ({ decile: num(d.decile) ?? 0, predicted: (num(d.mean_pd) ?? 0) * 100, observed: (num(d.observed_default_rate) ?? 0) * 100 }));
  const shap = arr(m.shap_importance).slice(0, 10).map((s) => ({ label: str(s.label) ?? "", v: num(s.mean_abs_shap) ?? 0 }));
  const bands = arr(m.pd_bands).length ? arr(m.pd_bands) : arr(card.pd_bands);
  const fairness = obj(m.fairness);
  const bench = obj(m.benchmark);
  const plots = ["model_roc.png", "model_calibration.png", "model_fairness.png"];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Model card"
        subtitle={str(m.algorithm) ?? "Probability-of-default model"}
        actions={
          <>
            <Chip tone="lime" className="font-mono">
              {str(card.model_version) ?? "unavailable"}
            </Chip>
            <Chip tone="outline">{str(card.explainer) ?? "SHAP"}</Chip>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="AUC" value={num(test.auc)?.toFixed(3) ?? "—"} sub={`Gini ${num(test.gini)?.toFixed(3) ?? "—"}`} />
        <StatTile label="KS" value={num(test.ks)?.toFixed(3) ?? "—"} sub="max separation" />
        <StatTile label="Brier" value={num(test.brier)?.toFixed(4) ?? "—"} sub="lower is better" />
        <StatTile label="ECE" value={num(test.ece)?.toFixed(4) ?? "—"} sub={`calibrated · n=${num(test.n)?.toLocaleString("en-IN") ?? "—"}`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Calibration by decile"
            subtitle="Predicted PD vs observed default rate (%)"
            action={<Legend items={[{ label: "Predicted", color: k.olive }, { label: "Observed", color: k.indigo }]} />}
          />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={cal} margin={{ left: -10, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={k.grid} />
                <XAxis dataKey="decile" tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v: number) => `${v.toFixed(0)}%`} tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  content={({ payload, label }) =>
                    payload?.length ? (
                      <TooltipBox
                        title={`Decile ${String(label)}`}
                        rows={[
                          { label: "Predicted", value: `${(num(payload[0]?.value) ?? 0).toFixed(2)}%`, color: k.olive },
                          { label: "Observed", value: `${(num(payload[1]?.value) ?? 0).toFixed(2)}%`, color: k.indigo },
                        ]}
                      />
                    ) : null
                  }
                />
                <Line dataKey="predicted" stroke={k.olive} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                <Line dataKey="observed" stroke={k.indigo} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardHeader title="Global feature importance" subtitle="Mean |SHAP| on the test set" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={shap} layout="vertical" margin={{ left: 0, right: 12, top: 0, bottom: 0 }} barSize={14}>
                <CartesianGrid horizontal={false} stroke={k.grid} />
                <XAxis type="number" tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="label" width={190} tick={{ fill: k.ink, fontSize: 11 }} tickFormatter={(v: string) => (v.length > 30 ? `${v.slice(0, 29)}…` : v)} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: k.grid }} content={({ payload }) => (payload?.[0] ? <TooltipBox rows={[{ label: String(payload[0].payload.label), value: (num(payload[0].value) ?? 0).toFixed(3), color: k.olive }]} /> : null)} />
                <Bar dataKey="v" fill={k.olive} radius={[0, 4, 4, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="PD bands → policy action" subtitle="How calibrated PD maps to grade, band and the model's suggested action" />
        <div className="-mx-4 overflow-x-auto sm:-mx-5">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead>
              <tr className="text-left text-xs text-graphite">
                {["Grade", "Band", "PD range", "Share of test", "Mean PD", "Observed default", "Model action"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium first:pl-5 last:pr-5">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bands.map((b) => (
                <tr key={str(b.grade)} className="border-t border-hairline">
                  <td className="py-2.5 pl-5 pr-3 font-display text-lg font-semibold text-ink">{str(b.grade)}</td>
                  <td className="px-3 text-graphite">{str(b.band)}</td>
                  <td className="px-3 tnum text-ink">{str(b.pd_range) ?? `≤ ${pct(num(b.max_pd))}`}</td>
                  <td className="px-3 tnum text-ink">{num(b.share) != null ? pct(num(b.share)) : "—"}</td>
                  <td className="px-3 tnum text-ink">{num(b.mean_pd) != null ? pct(num(b.mean_pd), 2) : "—"}</td>
                  <td className="px-3 tnum text-ink">{num(b.observed_default_rate) != null ? pct(num(b.observed_default_rate), 2) : "—"}</td>
                  <td className="py-2.5 pl-3 pr-5">
                    <Chip tone="outline" className="text-[11px]">
                      {str(b.policy_action) ?? str(b.action)}
                    </Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader title="Fairness" subtitle={str(fairness.approve_rule) ?? "Group metrics on the test set"} />
          <div className="space-y-4">
            {["gender", "age_band"].map((g) => {
              const f = obj(fairness[g]);
              const groups = Object.entries(obj(f.by_group));
              if (!groups.length) return null;
              return (
                <div key={g}>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Label>{g === "gender" ? "Gender" : "Age band"}</Label>
                    <Chip tone="outline" className="text-[11px]">
                      DP diff {num(f.demographic_parity_difference)?.toFixed(3) ?? "—"}
                    </Chip>
                    <Chip tone="outline" className="text-[11px]">
                      EO diff {num(f.equalized_odds_difference)?.toFixed(3) ?? "—"}
                    </Chip>
                  </div>
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="text-left text-xs text-graphite">
                        {["Group", "n", "Approval rate", "TPR", "AUC"].map((h) => (
                          <th key={h} className="py-1.5 pr-3 font-medium">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {groups.map(([name, v]) => {
                        const r = obj(v);
                        return (
                          <tr key={name} className="border-t border-hairline">
                            <td className="py-1.5 pr-3 font-medium text-ink">{name}</td>
                            <td className="pr-3 tnum text-graphite">{num(r.n)?.toLocaleString("en-IN")}</td>
                            <td className="pr-3 tnum text-ink">{pct(num(r.selection_rate))}</td>
                            <td className="pr-3 tnum text-ink">{pct(num(r.tpr))}</td>
                            <td className="tnum text-ink">{num(r.auc)?.toFixed(3)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
        </Card>
        <Card className="bg-sage lg:col-span-5">
          <CardHeader title="Limitations" subtitle="Read before relying on a score" />
          <ul className="space-y-2 text-sm text-ink">
            {LIMITATIONS.map((l) => (
              <li key={l} className="flex gap-2">
                <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-olive" />
                {l}
              </li>
            ))}
          </ul>
          {Object.keys(bench).length > 0 && (
            <div className="mt-4 rounded-surface bg-paper p-3">
              <Label className="block">Public benchmarks (method check)</Label>
              <ul className="mt-1.5 space-y-1 text-xs text-graphite">
                {Object.entries(bench).map(([name, v]) => (
                  <li key={name}>
                    {name.replace(/_/g, " ")}: AUC <span className="font-semibold text-ink tnum">{num(obj(v).auc)?.toFixed(3) ?? "—"}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Evaluation plots" subtitle="Generated by scripts/train_model.py" />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {plots.map((p) => (
            <figure key={p} className="overflow-hidden rounded-surface border border-hairline bg-white p-2">
              <img src={`${import.meta.env.BASE_URL}model-card/${p}`} alt={p.replace("model_", "").replace(".png", "") + " plot"} className="w-full" loading="lazy" />
            </figure>
          ))}
        </div>
      </Card>
      <p className="text-xs text-pewter">Training data: {str(card.training_data) ?? "synthetic"}.</p>
      <Disclaimer />
    </div>
  );
}
