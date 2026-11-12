import { ArrowRight, ArrowUpRight, Inbox, Plus, RefreshCw, RotateCcw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { inr, inrShort, ms, pct } from "@/lib/format";
import { OUTCOME_LABEL } from "@/lib/labels";
import { chartColors, useTheme } from "@/lib/theme";
import type { CaseSummary, DecisionOutcome } from "@/lib/types";
import { DECISION_OUTCOMES } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import { GradeChip, OutcomeChip } from "@/components/ui/Badges";
import { Avatar, Disclaimer, PageHeader } from "@/components/ui/misc";
import { Segmented } from "@/components/ui/Segmented";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { StatStrip, StatTile } from "@/components/ui/StatTile";
import { Donut } from "@/components/charts/Donut";
import { Legend, TooltipBox } from "@/components/charts/ChartTooltip";
import { outcomeColor } from "@/components/charts/outcomeColors";

type Filter = "ALL" | DecisionOutcome;

function count(cases: CaseSummary[], o: DecisionOutcome): number {
  return cases.filter((c) => c.outcome === o).length;
}

function ProductBars({ cases }: { cases: CaseSummary[] }) {
  const [theme] = useTheme();
  const c = chartColors(theme);
  const data = (["HOME_LOAN", "LAP"] as const).map((p) => {
    const row: Record<string, number | string> = { product: p === "HOME_LOAN" ? "Home loan" : "LAP" };
    DECISION_OUTCOMES.forEach((o) => {
      row[o] = cases.filter((x) => x.product === p && x.outcome === o).length;
    });
    return row;
  });
  return (
    <>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 0, right: 8, top: 4, bottom: 0 }} barSize={22}>
            <CartesianGrid horizontal={false} stroke={c.grid} />
            <XAxis type="number" allowDecimals={false} tick={{ fill: c.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="product" tick={{ fill: c.axis, fontSize: 12 }} axisLine={false} tickLine={false} width={84} />
            <Tooltip
              cursor={{ fill: c.grid }}
              content={({ payload, label }) =>
                payload?.length ? (
                  <TooltipBox
                    title={label}
                    rows={payload.map((p) => ({
                      label: OUTCOME_LABEL[p.dataKey as DecisionOutcome],
                      value: String(p.value),
                      color: outcomeColor(p.dataKey as DecisionOutcome, theme),
                    }))}
                  />
                ) : null
              }
            />
            {DECISION_OUTCOMES.map((o, i) => (
              <Bar
                key={o}
                dataKey={o}
                stackId="a"
                fill={outcomeColor(o, theme)}
                stroke={c.surface}
                strokeWidth={2}
                radius={i === DECISION_OUTCOMES.length - 1 ? [0, 6, 6, 0] : 0}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend items={DECISION_OUTCOMES.map((o) => ({ label: OUTCOME_LABEL[o], color: outcomeColor(o, theme) }))} />
    </>
  );
}

function CasesTable({ cases }: { cases: CaseSummary[] }) {
  const navigate = useNavigate();
  if (cases.length === 0) {
    return <EmptyState icon={Inbox} title="No cases match">Try another filter, or start a new case.</EmptyState>;
  }
  return (
    <div className="-mx-4 overflow-x-auto sm:-mx-5">
      <table className="w-full min-w-[920px] text-[13px]">
        <thead>
          <tr className="text-left text-xs text-graphite">
            {["Applicant", "Product", "Amount / property", "LTV", "Risk", "Flags", "Outcome", "TAT", ""].map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium first:pl-5 last:pr-5">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr
              key={c.id}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="cursor-pointer border-t border-hairline transition-colors hover:bg-fog/60"
            >
              <td className="py-3 pl-5 pr-3">
                <div className="flex items-center gap-3">
                  <Avatar name={c.applicant_name} />
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink">{c.applicant_name}</p>
                    <p className="truncate font-mono text-[11px] text-pewter">
                      {c.id}
                      {c.persona_id ? ` · ${c.persona_id}` : ""}
                    </p>
                  </div>
                </div>
              </td>
              <td className="px-3">
                <Chip tone={c.product === "LAP" ? "cyan" : "outline"}>{c.product === "LAP" ? "LAP" : "Home loan"}</Chip>
              </td>
              <td className="px-3 tnum">
                <span className="font-semibold text-ink">{inr(c.loan_amount)}</span>
                <span className="block text-xs text-pewter">on {inrShort(c.property_value)}</span>
              </td>
              <td className="px-3 tnum text-ink">{c.property_value ? pct(c.loan_amount / c.property_value) : "—"}</td>
              <td className="px-3">
                <div className="flex flex-col items-start gap-0.5">
                  <GradeChip grade={c.grade} />
                  <span className="text-[11px] text-pewter tnum">PD {c.pd != null ? pct(c.pd, 2) : "—"}</span>
                </div>
              </td>
              <td className="px-3">
                {c.flags > 0 ? <Chip tone="danger">{c.flags} flag{c.flags > 1 ? "s" : ""}</Chip> : <span className="text-xs text-pewter">None</span>}
              </td>
              <td className="px-3">
                <div className="flex flex-col items-start gap-0.5">
                  <OutcomeChip outcome={c.outcome} short />
                  {c.status === "OVERRIDDEN" && <span className="text-[11px] font-medium text-ember-dark">Overridden</span>}
                </div>
              </td>
              <td className="px-3 text-graphite tnum">{ms(c.turnaround_ms)}</td>
              <td className="py-3 pl-3 pr-5 text-right">
                <Link to={`/cases/${c.id}`} onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-semibold text-ink hover:underline">
                  Open <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Pipeline() {
  const [params, setParams] = useSearchParams();
  const filter = (params.get("filter") as Filter | null) ?? "ALL";
  const [query, setQuery] = useState("");
  const [theme] = useTheme();
  const cases = useAsync(() => api.listCases(), "cases");
  const portfolio = useAsync(() => api.portfolio(), "portfolio");
  const [resetting, setResetting] = useState(false);

  const list = useMemo(() => cases.data ?? [], [cases.data]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return list
      .filter((c) => filter === "ALL" || c.outcome === filter)
      .filter((c) => !q || c.applicant_name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || (c.persona_id ?? "").includes(q))
      .sort((a, b) => (a.persona_id ?? a.id).localeCompare(b.persona_id ?? b.id));
  }, [list, filter, query]);

  if (cases.error) return <ErrorState error={cases.error} onRetry={cases.reload} />;
  if (!cases.data) return <PageSkeleton />;

  const referred = count(list, "REFER");
  const avgTat = list.length ? list.reduce((a, c) => a + c.turnaround_ms, 0) / list.length : 0;
  const fraud = portfolio.data?.fraud_flagged ?? list.filter((c) => c.flags > 0).length;

  async function reset() {
    setResetting(true);
    try {
      const r = await api.resetDemo();
      toast.success(`Demo reset: ${r.cases} persona cases re-underwritten`);
      cases.reload();
      portfolio.reload();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Underwriting pipeline"
        subtitle="Every application, its explainable decision and what needs a human. Fully automated checks; you make the call."
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => { cases.reload(); portfolio.reload(); }}>
              <RefreshCw className={cn("size-4", cases.loading && "animate-spin")} aria-hidden /> Refresh
            </Button>
            <Button variant="secondary" size="sm" onClick={() => void reset()} disabled={resetting}>
              <RotateCcw className={cn("size-4", resetting && "animate-spin")} aria-hidden /> {resetting ? "Resetting…" : "Reset demo"}
            </Button>
            <ButtonLink to="/cases/new" variant="lime" data-testid="new-case-button">
              <Plus className="size-4" aria-hidden /> New case
            </ButtonLink>
          </>
        }
      />

      <StatStrip>
        <StatTile label="In queue" value={list.length} sub="cases on file" />
        <StatTile label="Approved" value={count(list, "APPROVE")} sub="clean approvals" />
        <StatTile label="Conditional" value={count(list, "APPROVE_WITH_CONDITIONS")} sub="with conditions" />
        <StatTile label="Referred" value={referred} sub="awaiting review" />
        <StatTile label="Declined" value={count(list, "DECLINE")} sub="with reasons" />
        <StatTile label="Avg TAT" value={ms(avgTat)} sub="docs → decision" />
        <StatTile label="Fraud flagged" value={fraud} sub="high severity" />
        <StatTile label="Sanctioned" value={inrShort(portfolio.data?.sanctioned_value ?? 0)} sub="approved value" />
      </StatStrip>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-5">
          <CardHeader title="Approval mix" subtitle="Engine and underwriter outcomes across the pipeline" />
          <Donut
            centerLabel="Cases"
            centerValue={String(list.length)}
            data={DECISION_OUTCOMES.map((o) => ({ key: o, label: OUTCOME_LABEL[o], value: count(list, o), color: outcomeColor(o, theme) }))}
          />
        </Card>
        <Card className="lg:col-span-4">
          <CardHeader title="Decisions by product" subtitle="Home loan vs loan against property" />
          <ProductBars cases={list} />
        </Card>
        <div className="relative flex min-h-[240px] flex-col justify-between overflow-hidden rounded-card border border-lime-dark/50 bg-lime p-6 text-on-lime lg:col-span-3">
          <div aria-hidden className="absolute -bottom-16 -right-16 size-56 rounded-full border-[18px] border-on-lime/5" />
          <div>
            <p className="text-sm font-medium text-on-lime/70">Review queue</p>
            <p className="mt-2 font-display text-[28px] font-semibold leading-[1.1]">
              <span className="mb-1 flex size-12 items-center justify-center rounded-full border-2 border-on-lime/80 tnum">{referred}</span>
              {referred === 1 ? "case needs" : "cases need"} you
            </p>
            <p className="mt-2 text-sm text-on-lime/75">Referred for human judgement: PEP match, thin buffers, borderline bureau.</p>
          </div>
          <button
            type="button"
            onClick={() => setParams({ filter: "REFER" })}
            className="relative mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-full bg-white text-sm font-semibold text-[#0d0d0d] hover:bg-white/85"
          >
            Show referred cases <ArrowUpRight className="size-4" aria-hidden />
          </button>
        </div>
      </div>

      <Card>
        <CardHeader
          title="Cases"
          subtitle={`${filtered.length} of ${list.length} shown`}
          display={false}
          action={
            <label className="relative">
              <span className="sr-only">Search cases</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-pewter" aria-hidden />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Name, case or persona"
                className="h-9 w-56 rounded-full border border-mist bg-paper pl-9 pr-3 text-sm text-ink placeholder:text-pewter"
              />
            </label>
          }
        />
        <Segmented<Filter>
          className="mb-3"
          size="sm"
          ariaLabel="Filter by outcome"
          role="radiogroup"
          value={filter}
          onChange={(v) => setParams(v === "ALL" ? {} : { filter: v })}
          items={[
            { value: "ALL", label: `All · ${list.length}` },
            ...DECISION_OUTCOMES.map((o) => ({ value: o, label: `${OUTCOME_LABEL[o]} · ${count(list, o)}` })),
          ]}
        />
        <CasesTable cases={filtered} />
      </Card>
      <Disclaimer />
    </div>
  );
}
