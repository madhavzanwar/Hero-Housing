import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { date, inr, inrShort, monthLabel, pct } from "@/lib/format";
import { chartColors, useTheme } from "@/lib/theme";
import type { CaseDetail, JsonObject } from "@/lib/types";
import { cn, num, str } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip, type Tone } from "@/components/ui/Chip";
import { StatTile } from "@/components/ui/StatTile";
import { Legend, TooltipBox } from "@/components/charts/ChartTooltip";

const CAT_TONE: Record<string, Tone> = {
  SALARY: "success",
  EMI: "info",
  BOUNCE: "danger",
  BOUNCE_CHARGE: "danger",
  CASH_DEPOSIT: "warning",
  GAMBLING: "danger",
  CRYPTO: "danger",
  BETTING: "danger",
  HIGH_RISK: "danger",
  RENT: "cyan",
  BUSINESS_CREDIT: "success",
};

function MonthlyChart({ c }: { c: CaseDetail }) {
  const [theme] = useTheme();
  const k = chartColors(theme);
  const data = c.bank.monthly.map((m) => ({ month: monthLabel(m.month), credits: m.credits, debits: m.debits }));
  return (
    <Card className="lg:col-span-8">
      <CardHeader title="Money in vs money out" subtitle={`${c.bank.months_covered} months of statement · monthly totals`} action={<Legend items={[{ label: "Credits", color: k.olive }, { label: "Debits", color: k.indigo }]} />} />
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={2} margin={{ left: 0, right: 4, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={k.grid} />
            <XAxis dataKey="month" tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={(v: number) => inrShort(v)} tick={{ fill: k.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
            <Tooltip
              cursor={{ fill: k.grid }}
              content={({ payload, label }) =>
                payload?.length ? (
                  <TooltipBox
                    title={label}
                    rows={[
                      { label: "Credits", value: inr(num(payload[0]?.value) ?? 0), color: k.olive },
                      { label: "Debits", value: inr(num(payload[1]?.value) ?? 0), color: k.indigo },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="credits" fill={k.olive} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
            <Bar dataKey="debits" fill={k.indigo} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function ListBlock({ title, rows, empty }: { title: string; rows: JsonObject[]; empty: string }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-graphite">{title}</p>
      {rows.length === 0 ? (
        <p className="text-xs text-pewter">{empty}</p>
      ) : (
        <ul className="space-y-1.5">
          {rows.slice(0, 6).map((r, i) => (
            <li key={i} className="flex items-center justify-between gap-2 rounded-xl bg-fog px-3 py-2 text-[13px]">
              <span className="min-w-0 truncate text-ink">
                {str(r.lender) ?? str(r.merchant) ?? str(r.description) ?? str(r.month) ?? str(r.date) ?? "—"}
                {str(r.date) && (str(r.lender) || str(r.merchant) || str(r.description)) && <span className="ml-1.5 text-[11px] text-pewter">{date(str(r.date))}</span>}
              </span>
              <span className="shrink-0 font-semibold tnum text-ink">{inr(Math.abs(num(r.amount) ?? num(r.total) ?? 0))}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Signals({ c }: { c: CaseDetail }) {
  const b = c.bank;
  return (
    <Card className="lg:col-span-4">
      <CardHeader title="Signals found" subtitle="Detected from transaction narrations" />
      <div className="space-y-4">
        <ListBlock title={`Existing EMIs · ${inr(b.total_detected_emi)}/mo`} rows={b.detected_emis} empty="No recurring EMIs detected" />
        <ListBlock title={`Bounces · ${b.bounces}`} rows={b.bounce_details} empty="No cheque / NACH returns" />
        <ListBlock title="Cash-deposit spikes" rows={b.cash_deposit_spikes} empty="No unusual cash deposits" />
        <ListBlock title="High-risk merchants" rows={b.high_risk_merchants} empty="No betting / crypto spends" />
        {b.notes.length > 0 && (
          <ul className="space-y-1 border-t border-hairline pt-3 text-xs text-graphite">
            {b.notes.map((n, i) => (
              <li key={i}>• {n}</li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function Transactions({ c }: { c: CaseDetail }) {
  const txns = c.bundle.transactions;
  const cats = useMemo(() => Array.from(new Set(txns.map((t) => t.category ?? "OTHER"))).sort(), [txns]);
  const [cat, setCat] = useState<string>("ALL");
  const shown = txns.filter((t) => cat === "ALL" || (t.category ?? "OTHER") === cat);
  return (
    <Card>
      <CardHeader title="Transactions" subtitle={`${txns.length} parsed from the bank statement · narrations PII-masked`} display={false} />
      <div className="mb-3 flex gap-1.5 overflow-x-auto pb-1" role="radiogroup" aria-label="Filter by category">
        {["ALL", ...cats].map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={cat === k}
            onClick={() => setCat(k)}
            className={cn(
              "min-h-8 shrink-0 rounded-full border px-3 text-xs font-medium",
              cat === k ? "border-lime-dark bg-lime text-on-lime" : "border-mist bg-paper text-graphite hover:text-ink",
            )}
          >
            {k === "ALL" ? `All · ${txns.length}` : `${k.replace(/_/g, " ").toLowerCase()} · ${txns.filter((t) => (t.category ?? "OTHER") === k).length}`}
          </button>
        ))}
      </div>
      <div className="-mx-4 max-h-[440px] overflow-auto sm:-mx-5">
        <table className="w-full min-w-[680px] text-[13px]">
          <thead className="sticky top-0 bg-surface">
            <tr className="text-left text-xs text-graphite">
              <th className="px-5 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Narration</th>
              <th className="px-3 py-2 font-medium">Category</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-5 py-2 text-right font-medium">Balance</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((t, i) => (
              <tr key={i} className="border-t border-hairline">
                <td className="whitespace-nowrap px-5 py-2 text-graphite tnum">{date(t.date)}</td>
                <td className="max-w-[320px] truncate px-3 py-2 text-ink" title={t.description}>
                  {t.description}
                </td>
                <td className="px-3 py-2">
                  <Chip tone={CAT_TONE[t.category ?? ""] ?? "neutral"} className="text-[11px]">
                    {(t.category ?? "Other").replace(/_/g, " ").toLowerCase()}
                  </Chip>
                </td>
                <td className={cn("whitespace-nowrap px-3 py-2 text-right font-semibold tnum", t.amount >= 0 ? "text-ok" : "text-ink")}>
                  {t.amount >= 0 ? "+" : "−"}
                  {inr(Math.abs(t.amount))}
                </td>
                <td className="whitespace-nowrap px-5 py-2 text-right text-graphite tnum">{t.balance != null ? inr(t.balance) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function BankTab({ c }: { c: CaseDetail }) {
  const b = c.bank;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Avg monthly balance" value={inrShort(b.avg_monthly_balance)} sub={`min ${inr(b.min_balance)}`} />
        <StatTile label="Avg salary credit" value={inrShort(b.avg_salary_credit || b.income_estimate)} sub={`income est. ${inrShort(b.income_estimate)}/mo`} />
        <StatTile
          label="Regularity"
          value={pct(b.salary_regularity, 0)}
          sub="months with salary credit"
          status={b.salary_regularity >= 0.8 ? { tone: "success", text: "Steady" } : { tone: "warning", text: "Irregular" }}
        />
        <StatTile label="EMIs detected" value={b.detected_emis.length} sub={`${inr(b.total_detected_emi)}/mo`} />
        <StatTile label="Bounces" value={b.bounces} sub="cheque / NACH returns" status={b.bounces === 0 ? { tone: "success", text: "None" } : { tone: "danger", text: "Seen" }} />
        <StatTile
          label="Cash share"
          value={pct(b.cash_deposit_share, 0)}
          sub={`${inrShort(b.cash_deposit_total)} cash deposits`}
          status={b.cash_deposit_share >= 0.3 ? { tone: "warning", text: "High" } : undefined}
        />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <MonthlyChart c={c} />
        <Signals c={c} />
      </div>
      <Transactions c={c} />
    </div>
  );
}
