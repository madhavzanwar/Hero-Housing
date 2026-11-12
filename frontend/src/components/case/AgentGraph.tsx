import {
  Banknote,
  Calculator,
  FileCheck2,
  FileSearch,
  FileText,
  Gauge as GaugeIcon,
  Inbox,
  Lock,
  ScanText,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { NODE_LABEL } from "@/lib/labels";
import { ms } from "@/lib/format";
import { cn } from "@/lib/utils";

export type NodeState = "waiting" | "running" | "done" | "error";

export interface GraphStep {
  node: string;
  state: NodeState;
  ms?: number;
  summary?: string;
}

const ICONS: Record<string, LucideIcon> = {
  intake: Inbox,
  documents: ScanText,
  missing_docs_check: FileSearch,
  bank_analytics: Banknote,
  eligibility: Calculator,
  fraud_compliance: ShieldAlert,
  risk_model: Sparkles,
  capacity: GaugeIcon,
  decision: FileCheck2,
  credit_memo: FileText,
  audit: Lock,
};

const STATE_TEXT: Record<NodeState, string> = { waiting: "Waiting", running: "Working…", done: "Done", error: "Error" };

function NodeBubble({ step, index }: { step: GraphStep; index: number }) {
  const Icon = ICONS[step.node] ?? Sparkles;
  return (
    <div className="flex w-[120px] flex-col items-center text-center">
      <span
        className={cn(
          "relative flex size-12 items-center justify-center rounded-full border bg-paper shadow-sm transition-all duration-300",
          step.state === "done" && "border-lime-dark bg-lime text-on-lime",
          step.state === "running" && "border-lime-dark text-ink ring-4 ring-lime/40",
          step.state === "waiting" && "border-hairline text-pewter",
          step.state === "error" && "border-bad-solid text-bad",
        )}
      >
        {step.state === "running" ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Icon className="size-5" strokeWidth={1.75} aria-hidden />}
        <span className="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full border border-hairline bg-paper text-[10px] font-semibold text-graphite tnum">
          {index + 1}
        </span>
      </span>
      <span className="mt-1.5 text-xs font-semibold leading-tight text-ink">{NODE_LABEL[step.node] ?? step.node}</span>
      <span className="text-[11px] text-pewter tnum">
        {step.state === "done" && step.ms != null ? ms(step.ms) : STATE_TEXT[step.state]}
      </span>
    </div>
  );
}

/** Radial LangGraph trace (FinPilot Evidence Council), list on small screens. */
export function AgentGraph({ steps, centerTitle, centerText }: { steps: GraphStep[]; centerTitle: string; centerText: string }) {
  const n = steps.length;
  const done = steps.filter((s) => s.state === "done").length;
  return (
    <div>
      <div
        className="relative mx-auto hidden aspect-square w-full max-w-[600px] rounded-card border border-hairline sm:block"
        style={{ background: "radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--color-lime) 22%, transparent), transparent 70%)" }}
      >
        <svg className="absolute inset-0 size-full" viewBox="0 0 100 100" aria-hidden>
          {steps.map((s, i) => {
            const a = (i / n) * 2 * Math.PI - Math.PI / 2;
            return (
              <line
                key={s.node}
                x1={50}
                y1={50}
                x2={50 + 38 * Math.cos(a)}
                y2={50 + 38 * Math.sin(a)}
                strokeWidth={0.35}
                className={cn("transition-colors", s.state === "done" ? "stroke-lime-dark" : "stroke-steel/50")}
                strokeDasharray={s.state === "done" ? undefined : "1 1"}
              />
            );
          })}
        </svg>
        <div className="absolute left-1/2 top-1/2 w-40 -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-hairline bg-paper p-3 shadow-md">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-ink">
            <FileText className="size-3.5 text-ok" aria-hidden /> {centerTitle}
          </p>
          <div className="my-2 space-y-1" aria-hidden>
            {[90, 70, 80, 55].map((w, i) => (
              <div key={i} className="h-1.5 rounded-full bg-fog" style={{ width: `${w}%` }} />
            ))}
          </div>
          <p className="text-[11px] text-graphite">{centerText}</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-fog">
            <div className="h-full rounded-full bg-lime transition-[width] duration-500" style={{ width: `${(done / n) * 100}%` }} />
          </div>
        </div>
        {steps.map((s, i) => {
          const a = (i / n) * 2 * Math.PI - Math.PI / 2;
          return (
            <div
              key={s.node}
              className="absolute -translate-x-1/2 -translate-y-[24px]"
              style={{ left: `${50 + 40 * Math.cos(a)}%`, top: `${50 + 40 * Math.sin(a)}%` }}
            >
              <NodeBubble step={s} index={i} />
            </div>
          );
        })}
      </div>

      <ol className="space-y-2 sm:hidden">
        {steps.map((s, i) => (
          <li key={s.node} className="flex items-center gap-3 rounded-surface bg-fog px-3 py-2">
            <span className="w-5 text-xs text-pewter tnum">{i + 1}</span>
            <span className="flex-1 text-sm font-medium text-ink">{NODE_LABEL[s.node] ?? s.node}</span>
            {s.state === "done" ? (
              <span className="flex items-center gap-1 text-xs text-ok">
                <CheckCircle2 className="size-3.5" aria-hidden /> {s.ms != null ? ms(s.ms) : "Done"}
              </span>
            ) : s.state === "running" ? (
              <Loader2 className="size-4 animate-spin text-olive" aria-label="Working" />
            ) : (
              <span className="text-xs text-pewter">{STATE_TEXT[s.state]}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
