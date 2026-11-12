import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { inrShort } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CopilotChat } from "@/components/copilot/CopilotChat";
import { OutcomeChip } from "@/components/ui/Badges";
import { ErrorState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";

export default function Copilot() {
  const [params, setParams] = useSearchParams();
  const cases = useAsync(() => api.listCases(), "cases");
  const sorted = [...(cases.data ?? [])].sort((a, b) => (a.persona_id ?? a.id).localeCompare(b.persona_id ?? b.id));
  const [selected, setSelected] = useState<string | null>(params.get("case"));
  const current = selected ?? sorted.find((c) => c.outcome === "REFER")?.id ?? sorted[0]?.id ?? null;
  const sel = sorted.find((c) => c.id === current);

  useEffect(() => {
    if (selected) setParams({ case: selected }, { replace: true });
  }, [selected, setParams]);

  if (cases.error) return <ErrorState error={cases.error} onRetry={cases.reload} />;
  if (!cases.data) return <PageSkeleton />;

  return (
    <div className="grid min-h-[calc(100vh-7rem)] grid-cols-1 overflow-hidden rounded-card border border-hairline bg-surface shadow-sm lg:grid-cols-[300px_1fr]">
      <aside className="border-b border-hairline bg-sage/60 p-4 lg:border-b-0 lg:border-r" aria-label="Cases">
        <p className="mb-1 px-1 font-display text-lg font-medium text-ink">Cases</p>
        <p className="mb-3 px-1 text-xs text-graphite">Pick the case the Copilot should read.</p>
        <ul className="flex gap-2 overflow-x-auto pb-1 lg:max-h-[calc(100vh-14rem)] lg:flex-col lg:overflow-y-auto">
          {sorted.map((c) => {
            const active = c.id === current;
            return (
              <li key={c.id} className="shrink-0 lg:shrink">
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "w-56 rounded-2xl border px-3 py-2.5 text-left transition-colors lg:w-full",
                    active ? "border-lime-dark bg-paper shadow-sm" : "border-transparent hover:bg-paper/60",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-ink">{c.applicant_name}</span>
                    {active && <span className="size-2 shrink-0 rounded-full bg-ember" aria-hidden />}
                  </span>
                  <span className="mt-1 flex items-center gap-2">
                    <OutcomeChip outcome={c.outcome} short />
                    <span className="text-[11px] text-pewter">
                      {c.product === "LAP" ? "LAP" : "HL"} {inrShort(c.loan_amount)}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>
      <section className="flex min-h-[560px] min-w-0 flex-col p-4 sm:p-6">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-graphite">
            Underwriting Copilot <span className="text-pewter">· grounded</span>
          </p>
          {sel && (
            <Link to={`/cases/${sel.id}`} className="font-mono text-xs text-graphite hover:text-ink">
              {sel.id} →
            </Link>
          )}
        </div>
        {current ? (
          <CopilotChat caseId={current} greeting={sel ? `Hey, underwriter. Let's look at ${sel.applicant_name.split(" ")[0]}'s case.` : undefined} />
        ) : (
          <p className="m-auto text-sm text-pewter">No cases yet. Start one from New case.</p>
        )}
      </section>
    </div>
  );
}
