import type { CaseDetail } from "@/lib/types";
import { dateTime, ms } from "@/lib/format";
import { NODE_LABEL } from "@/lib/labels";
import { cn, humanize } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip, type Tone } from "@/components/ui/Chip";
import { Mono } from "@/components/ui/misc";

function actorTone(actor: string): Tone {
  if (actor.startsWith("underwriter")) return "accent";
  if (actor === "ml-model") return "info";
  if (actor === "copilot") return "lime";
  return "neutral";
}

export function AuditTab({ c }: { c: CaseDetail }) {
  const total = c.copilot_trace.reduce((a, t) => a + t.ms, 0);
  const maxMs = Math.max(1, ...c.copilot_trace.map((t) => t.ms));
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <Card className="xl:col-span-7">
        <CardHeader title="Audit trail" subtitle={`${c.audit.length} events · each hash = sha256(previous hash + event)`} />
        <ol className="relative ml-2 border-l border-mist">
          {c.audit.map((e, i) => (
            <li key={i} className="relative pb-5 pl-5 last:pb-0">
              <span
                aria-hidden
                className={cn(
                  "absolute -left-[5px] top-1.5 size-2.5 rounded-full ring-4 ring-surface",
                  e.action === "OVERRIDE" ? "bg-ember" : e.action === "DECISION" ? "bg-lime-dark" : "bg-steel",
                )}
              />
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={actorTone(e.actor)} className="text-[11px]">
                  {e.actor}
                </Chip>
                <span className="text-[13px] font-semibold text-ink">{humanize(e.action)}</span>
                <span className="ml-auto text-[11px] text-pewter tnum">{dateTime(e.at)}</span>
              </div>
              <p className="mt-1 text-[13px] text-graphite">{e.detail}</p>
              {e.hash && <Mono className="mt-0.5 block text-pewter">#{e.hash.slice(0, 16)}</Mono>}
            </li>
          ))}
        </ol>
      </Card>

      <Card className="xl:col-span-5">
        <CardHeader title="Agent trace" subtitle={`LangGraph Underwriting Copilot · ${ms(total)} total`} />
        <div className="-mx-4 overflow-x-auto sm:-mx-5">
          <table className="w-full min-w-[420px] text-[13px]">
            <thead>
              <tr className="text-left text-xs text-graphite">
                <th className="px-5 py-2 font-medium">Node</th>
                <th className="px-3 py-2 font-medium">What it did</th>
                <th className="px-5 py-2 text-right font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {c.copilot_trace.map((t, i) => (
                <tr key={i} className="border-t border-hairline align-top">
                  <td className="whitespace-nowrap px-5 py-2.5">
                    <span className="flex items-center gap-2">
                      <span className="w-4 text-[11px] text-pewter tnum">{i + 1}</span>
                      <span className="font-semibold text-ink">{NODE_LABEL[t.node] ?? t.node}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-graphite">{t.summary}</td>
                  <td className="px-5 py-2.5 text-right">
                    <span className="block text-ink tnum">{ms(t.ms)}</span>
                    <span className="mt-1 ml-auto block h-1 w-14 overflow-hidden rounded-full bg-fog">
                      <span className="block h-full rounded-full bg-olive" style={{ width: `${(t.ms / maxMs) * 100}%` }} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
