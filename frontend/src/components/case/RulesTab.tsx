import { useState } from "react";
import type { CaseDetail, RuleOutcome } from "@/lib/types";
import { cn, humanize } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { RuleOutcomeChip } from "@/components/ui/Badges";
import { Disclaimer, RuleId } from "@/components/ui/misc";

type Filter = "ALL" | "ISSUES" | RuleOutcome;
const ORDER: Record<RuleOutcome, number> = { FAIL: 0, WARN: 1, INFO: 2, PASS: 3 };

export function RulesTab({ c }: { c: CaseDetail }) {
  const [filter, setFilter] = useState<Filter>("ALL");
  const rules = [...c.decision.rules_fired].sort((a, b) => ORDER[a.outcome] - ORDER[b.outcome]);
  const shown = rules.filter((r) => filter === "ALL" || (filter === "ISSUES" ? r.outcome === "FAIL" || r.outcome === "WARN" : r.outcome === filter));
  const n = (o: RuleOutcome) => rules.filter((r) => r.outcome === o).length;
  const filters: { v: Filter; label: string }[] = [
    { v: "ALL", label: `All · ${rules.length}` },
    { v: "ISSUES", label: `Fail + warn · ${n("FAIL") + n("WARN")}` },
    { v: "FAIL", label: `Fail · ${n("FAIL")}` },
    { v: "WARN", label: `Warn · ${n("WARN")}` },
    { v: "PASS", label: `Pass · ${n("PASS")}` },
  ];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Rules fired" subtitle={`Machine-readable policy ${c.decision.policy_version}. Every rule ID maps to a key in policy_v1.yaml.`} />
        <div className="mb-3 flex gap-1.5 overflow-x-auto pb-1" role="radiogroup" aria-label="Filter rules">
          {filters.map((f) => (
            <button
              key={f.v}
              type="button"
              role="radio"
              aria-checked={filter === f.v}
              onClick={() => setFilter(f.v)}
              className={cn(
                "min-h-8 shrink-0 rounded-full border px-3 text-xs font-medium",
                filter === f.v ? "border-lime-dark bg-lime text-on-lime" : "border-mist bg-paper text-graphite hover:text-ink",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="-mx-4 overflow-x-auto sm:-mx-5">
          <table className="w-full min-w-[980px] text-[13px]">
            <thead>
              <tr className="text-left text-xs text-graphite">
                <th className="px-5 py-2 font-medium">Rule</th>
                <th className="px-3 py-2 font-medium">Category</th>
                <th className="px-3 py-2 font-medium">Outcome</th>
                <th className="px-3 py-2 font-medium">Detail</th>
                <th className="px-3 py-2 font-medium">Effect</th>
                <th className="px-5 py-2 font-medium">Reference</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={`${r.rule_id}-${i}`} className="border-t border-hairline align-top">
                  <td className="px-5 py-3">
                    <RuleId id={r.rule_id} />
                    <p className="mt-1 max-w-[200px] text-xs font-medium text-ink">{r.name}</p>
                  </td>
                  <td className="px-3 py-3">
                    <Chip tone="outline" className="text-[11px]">
                      {humanize(r.category)}
                    </Chip>
                  </td>
                  <td className="px-3 py-3">
                    <RuleOutcomeChip outcome={r.outcome} />
                  </td>
                  <td className="max-w-[380px] px-3 py-3 text-graphite">{r.detail}</td>
                  <td className="px-3 py-3">
                    {r.effect === "NONE" ? (
                      <span className="text-xs text-pewter">—</span>
                    ) : (
                      <Chip tone={r.effect === "DECLINE" ? "danger" : r.effect === "REFER" ? "info" : "warning"} className="text-[11px]">
                        {humanize(r.effect)}
                      </Chip>
                    )}
                  </td>
                  <td className="max-w-[240px] px-5 py-3">
                    <p className="line-clamp-2 text-[11px] text-pewter" title={r.reference ?? undefined}>
                      {r.reference ?? "—"}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Disclaimer text={c.disclaimer} />
    </div>
  );
}
