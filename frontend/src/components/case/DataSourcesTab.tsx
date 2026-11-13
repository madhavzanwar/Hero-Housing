import {
  Building2,
  ChevronDown,
  Cpu,
  Database,
  FileBadge,
  Fingerprint,
  Globe2,
  Landmark,
  MapPinned,
  ShieldAlert,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { CaseDetail, DataSourceResult, SourceMode, SourceStatus } from "@/lib/types";
import { dateTime, ms } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip, type Tone } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { Mono } from "@/components/ui/misc";

export const SOURCE_META: Record<string, { label: string; icon: LucideIcon }> = {
  CIBIL_BUREAU: { label: "CIBIL bureau", icon: Landmark },
  NSDL_PAN: { label: "NSDL PAN", icon: FileBadge },
  UIDAI_OKYC: { label: "UIDAI OKYC", icon: Fingerprint },
  ACCOUNT_AGGREGATOR: { label: "Account Aggregator", icon: Wallet },
  CERSAI: { label: "CERSAI", icon: Database },
  SANCTIONS_UN: { label: "UN / PEP sanctions", icon: ShieldAlert },
  GSTN_MCA: { label: "GSTN / MCA", icon: Building2 },
  CIRCLE_RATE: { label: "Circle rate", icon: MapPinned },
};

export function sourceLabel(s: DataSourceResult): string {
  return SOURCE_META[s.source]?.label ?? s.source.replace(/_/g, " ");
}

const STATUS_TONE: Record<SourceStatus, Tone> = { OK: "success", NO_MATCH: "neutral", HIT: "danger", ERROR: "warning", SKIPPED: "outline" };
const STATUS_TEXT: Record<SourceStatus, string> = { OK: "OK", NO_MATCH: "No match", HIT: "Hit", ERROR: "Error", SKIPPED: "Skipped" };
const MODE_TEXT: Record<SourceMode, string> = { LIVE: "Live", SANDBOX_MOCK: "Sandbox mock", OFFLINE_DATASET: "Offline dataset" };

export function SourceStatusChip({ s }: { s: DataSourceResult }) {
  return (
    <Chip tone={STATUS_TONE[s.status]} className="text-[11px]">
      {STATUS_TEXT[s.status]}
    </Chip>
  );
}

const ROW = 76;

/** Left-to-right flow: sources → engine → decision (FinPilot evidence-room style). */
function SourceFlow({ c }: { c: CaseDetail }) {
  const sources = c.data_sources ?? [];
  const n = sources.length;
  const height = Math.max(n * ROW, 320);
  const mid = height / 2;
  const total = sources.reduce((a, s) => a + s.latency_ms, 0);
  const maxLatency = Math.max(0, ...sources.map((s) => s.latency_ms));
  return (
    <div>
      {/* desktop flow */}
      <div className="hidden md:grid md:grid-cols-[minmax(0,1.25fr)_120px_minmax(0,0.75fr)] md:items-start">
        <ol className="relative" style={{ height }}>
          {sources.map((s, i) => {
            const meta = SOURCE_META[s.source];
            const Icon = meta?.icon ?? Globe2;
            return (
              <li
                key={s.source}
                className={cn(
                  "absolute inset-x-0 flex items-center gap-3 rounded-2xl border bg-paper px-3 py-2 shadow-sm",
                  s.status === "HIT" ? "border-bad-solid/40" : s.status === "ERROR" ? "border-warn-solid/40" : "border-hairline",
                )}
                style={{ top: i * ROW + (ROW - 64) / 2, height: 64 }}
              >
                <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full", s.status === "HIT" ? "bg-bad-soft text-bad" : "bg-sage text-ink")}>
                  <Icon className="size-4" strokeWidth={1.75} aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-[13px] font-semibold text-ink">{sourceLabel(s)}</span>
                    <SourceStatusChip s={s} />
                  </span>
                  <span className="block truncate text-[11px] text-graphite" title={s.summary}>
                    {s.summary}
                  </span>
                </span>
                <span className="hidden shrink-0 text-right lg:block">
                  <span className="block text-xs font-semibold text-ink tnum">{ms(s.latency_ms)}</span>
                  <span className="block text-[10px] text-pewter">{MODE_TEXT[s.mode]}</span>
                </span>
              </li>
            );
          })}
        </ol>
        <svg viewBox={`0 0 120 ${height}`} preserveAspectRatio="none" className="h-full w-full" style={{ height }} aria-hidden>
          {sources.map((s, i) => {
            const y = i * ROW + ROW / 2;
            return (
              <path
                key={s.source}
                d={`M0 ${y} C 60 ${y}, 60 ${mid}, 120 ${mid}`}
                fill="none"
                strokeWidth={s.status === "HIT" ? 2 : 1.5}
                className={s.status === "HIT" ? "stroke-bad-solid" : s.status === "ERROR" ? "stroke-warn-solid" : "stroke-lime-dark"}
                strokeDasharray={s.status === "SKIPPED" ? "4 4" : undefined}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>
        <div className="flex flex-col justify-center" style={{ height }}>
          <div className="rounded-3xl border border-lime-dark/50 bg-lime p-5 text-on-lime shadow-[0_10px_30px_-12px_rgba(95,127,12,0.6)]">
            <span className="flex size-10 items-center justify-center rounded-full bg-white/60">
              <Cpu className="size-5" aria-hidden />
            </span>
            <p className="mt-3 font-display text-xl font-semibold">Underwriting engine</p>
            <p className="mt-1 text-xs text-on-lime/75">Rules + PD model + Monte Carlo</p>
            <dl className="mt-3 space-y-1 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="text-on-lime/70">Sources</dt>
                <dd className="font-semibold tnum">{n}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-on-lime/70">Parallel wall time</dt>
                <dd className="font-semibold tnum">{ms(maxLatency)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-on-lime/70">Sum of calls</dt>
                <dd className="font-semibold tnum">{ms(total)}</dd>
              </div>
            </dl>
          </div>
          <p className="mt-3 text-center text-[11px] text-pewter">→ eligibility · fraud/KYC · risk · property → decision</p>
        </div>
      </div>

      {/* mobile list */}
      <ul className="space-y-2 md:hidden">
        {sources.map((s) => (
          <li key={s.source} className="flex items-center justify-between gap-2 rounded-surface bg-fog px-3 py-2">
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-ink">{sourceLabel(s)}</span>
              <span className="block truncate text-[11px] text-graphite">{s.summary}</span>
            </span>
            <SourceStatusChip s={s} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function SourceTable({ c }: { c: CaseDetail }) {
  const sources = c.data_sources ?? [];
  return (
    <Card>
      <CardHeader title="Source calls" subtitle="Consent-bound, purpose-limited pulls. Payloads are stored masked only." />
      <ul className="divide-y divide-hairline">
        {sources.map((s) => (
          <li key={s.source}>
            <details className="group py-3">
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-1.5 [&::-webkit-details-marker]:hidden">
                <span className="min-w-[180px] flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{sourceLabel(s)}</span>
                    <SourceStatusChip s={s} />
                  </span>
                  <span className="block text-xs text-pewter">{s.provider}</span>
                </span>
                <span className="w-full text-[13px] text-graphite md:w-auto md:max-w-[380px] md:flex-[2]">{s.summary}</span>
                <Chip tone="outline" className="text-[11px]">
                  {MODE_TEXT[s.mode]}
                </Chip>
                <span className="w-16 text-right text-xs font-semibold text-ink tnum">{ms(s.latency_ms)}</span>
                <ChevronDown className="size-4 text-pewter transition-transform group-open:rotate-180" aria-hidden />
              </summary>
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[260px_1fr]">
                <dl className="space-y-1.5 rounded-surface bg-fog p-3 text-xs">
                  <div>
                    <dt className="text-pewter">Consent ID</dt>
                    <dd>
                      <Mono className="text-ink">{s.consent_id ?? "— (not consent-gated)"}</Mono>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-pewter">Request ref</dt>
                    <dd>
                      <Mono className="text-ink">{s.request_ref || "—"}</Mono>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-pewter">Fetched</dt>
                    <dd className="text-ink">{dateTime(s.fetched_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-pewter">Kind</dt>
                    <dd className="text-ink">{s.kind}</dd>
                  </div>
                </dl>
                <pre className="max-h-72 overflow-auto rounded-surface bg-fog p-3 font-mono text-[11px] leading-relaxed text-ink">
                  {JSON.stringify(s.data, null, 2)}
                </pre>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Compact strip for the Decision tab. */
export function SourceStrip({ c, onOpen }: { c: CaseDetail; onOpen: () => void }) {
  const sources = c.data_sources ?? [];
  if (!sources.length) return null;
  const hits = sources.filter((s) => s.status === "HIT").length;
  return (
    <Card className="py-3 sm:py-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm font-semibold text-ink">Data sources</span>
        <span className="mr-2 text-xs text-pewter">
          {sources.length} pulled · {hits ? `${hits} hit${hits > 1 ? "s" : ""}` : "no hits"}
        </span>
        {sources.map((s) => {
          const Icon = SOURCE_META[s.source]?.icon ?? Globe2;
          return (
            <span
              key={s.source}
              title={`${sourceLabel(s)}: ${s.summary}`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
                s.status === "HIT" ? "border-bad-solid/30 bg-bad-soft text-bad" : s.status === "ERROR" ? "border-warn-solid/30 bg-warn-soft text-warn" : "border-hairline bg-fog text-graphite",
              )}
            >
              <Icon className="size-3.5" aria-hidden />
              {sourceLabel(s)} · {STATUS_TEXT[s.status]}
            </span>
          );
        })}
        <button type="button" onClick={onOpen} className="ml-auto text-xs font-semibold text-ink hover:underline">
          Data flow →
        </button>
      </div>
    </Card>
  );
}

export function DataSourcesTab({ c }: { c: CaseDetail }) {
  const sources = c.data_sources ?? [];
  if (!sources.length) {
    return (
      <Card>
        <EmptyState icon={Database} title="No external data sources on this case">
          This case was underwritten before data-source integration, or the sources were skipped. Re-run it to pull bureau, KYC, AA, CERSAI and screening data.
        </EmptyState>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="How data flows into the engine"
          subtitle="Every external source is called in parallel with a per-source timeout; failures degrade to a refer, never a silent pass."
          action={
            <span className="flex flex-wrap gap-1.5">
              <Chip tone="outline">Sandbox mocks + offline datasets</Chip>
              <Chip tone="success">DPDP consent-bound</Chip>
            </span>
          }
        />
        <SourceFlow c={c} />
      </Card>
      <SourceTable c={c} />
    </div>
  );
}
