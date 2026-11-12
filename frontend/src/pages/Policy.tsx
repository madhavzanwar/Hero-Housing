import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { Json, JsonObject } from "@/lib/types";
import { humanize, isRecord, str } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/EmptyState";
import { Disclaimer, PageHeader, RuleId } from "@/components/ui/misc";
import { PageSkeleton } from "@/components/ui/Skeleton";

const SKIP = new Set(["version", "effective_from", "owner", "currency", "references", "rules"]);

function fmt(v: Json): string {
  if (v === null) return "none";
  if (typeof v === "number") return Math.abs(v) >= 1000 ? v.toLocaleString("en-IN") : String(v);
  if (typeof v === "string" || typeof v === "boolean") return String(v);
  if (Array.isArray(v) && v.every((x) => !isRecord(x))) return v.map((x) => fmt(x)).join(", ");
  return JSON.stringify(v);
}

/** Flatten nested YAML into dotted key/value rows (arrays of objects get [i]). */
function flatten(obj: Json, prefix = "", out: [string, string][] = []): [string, string][] {
  if (isRecord(obj)) {
    for (const [k, v] of Object.entries(obj)) flatten(v as Json, prefix ? `${prefix}.${k}` : k, out);
  } else if (Array.isArray(obj) && obj.some((x) => isRecord(x))) {
    obj.forEach((x, i) => {
      const id = isRecord(x) ? str(x.id) : undefined;
      flatten(x, `${prefix}[${id ?? i}]`, out);
    });
  } else {
    out.push([prefix, fmt(obj)]);
  }
  return out;
}

function SectionCard({ name, value }: { name: string; value: Json }) {
  const rows = flatten(value);
  return (
    <Card>
      <CardHeader title={humanize(name)} subtitle={`${rows.length} parameters`} action={<Chip tone="outline" className="font-mono text-[11px]">{name}</Chip>} />
      <div className="max-h-[360px] overflow-auto">
        <table className="w-full text-[12px]">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k} className="border-t border-hairline first:border-t-0 align-top">
                <td className="w-1/2 break-all py-1.5 pr-3 font-mono text-[11px] text-graphite">{k}</td>
                <td className="break-words py-1.5 font-mono text-[11px] font-medium text-ink">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function Policy() {
  const res = useAsync(() => api.policy(), "policy");
  const [q, setQ] = useState("");
  const p = res.data?.policy;
  const rulesMeta = useMemo(() => (p && isRecord(p.rules) ? (p.rules as Record<string, JsonObject>) : {}), [p]);
  const refs = p && isRecord(p.references) ? (p.references as Record<string, Json>) : {};
  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data || !p) return <PageSkeleton />;
  const sections = Object.entries(p).filter(([k]) => !SKIP.has(k));
  const ruleRows = Object.entries(rulesMeta).filter(([id, r]) => !q || `${id} ${str(r.name) ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Credit policy"
        subtitle="The machine-readable policy every decision is computed from. Engines read thresholds from this file; nothing is hard-coded."
        actions={
          <>
            <Chip tone="lime">Version {res.data.version}</Chip>
            {str(p.effective_from) && <Chip tone="outline">Effective {str(p.effective_from)}</Chip>}
            {str(p.owner) && <Chip tone="outline">{str(p.owner)}</Chip>}
          </>
        }
      />

      <Card>
        <CardHeader
          title="Rule catalogue"
          subtitle={`${Object.keys(rulesMeta).length} rule IDs with their category and regulatory basis`}
          action={
            <label>
              <span className="sr-only">Filter rules</span>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter, e.g. FOIR" className="h-9 w-48 rounded-full border border-mist bg-paper px-3 text-sm text-ink placeholder:text-pewter" />
            </label>
          }
        />
        <div className="-mx-4 max-h-[420px] overflow-auto sm:-mx-5">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-xs text-graphite">
                <th className="px-5 py-2 font-medium">Rule</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Category</th>
                <th className="px-5 py-2 font-medium">Reference</th>
              </tr>
            </thead>
            <tbody>
              {ruleRows.map(([id, r]) => {
                const ref = str(r.ref);
                const refText = ref ? (str(refs[ref]) ?? ref) : "—";
                return (
                  <tr key={id} className="border-t border-hairline align-top">
                    <td className="px-5 py-2">
                      <RuleId id={id} />
                    </td>
                    <td className="px-3 py-2 text-ink">{str(r.name)}</td>
                    <td className="px-3 py-2">
                      <Chip tone="outline" className="text-[11px]">
                        {humanize(str(r.category) ?? "")}
                      </Chip>
                    </td>
                    <td className="max-w-[360px] px-5 py-2">
                      <p className="line-clamp-2 text-[11px] text-pewter" title={refText}>
                        {refText}
                      </p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sections.map(([k, v]) => (
          <SectionCard key={k} name={k} value={v} />
        ))}
      </div>

      <Card>
        <CardHeader title="Regulatory references" subtitle="Cited by rule IDs in decisions, memos and letters" />
        <dl className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {Object.entries(refs).map(([k, v]) => (
            <div key={k} className="rounded-surface bg-fog p-3">
              <dt className="font-mono text-[11px] font-semibold text-ink">{k}</dt>
              <dd className="mt-1 text-xs text-graphite">{fmt(v)}</dd>
            </div>
          ))}
        </dl>
      </Card>
      <Disclaimer text="Demonstration policy calibrated to public RBI/NHB guidance; not a lender's actual credit policy." />
    </div>
  );
}
