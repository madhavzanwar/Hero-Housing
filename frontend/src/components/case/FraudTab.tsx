import { CheckCircle2, ShieldCheck } from "lucide-react";
import type { CaseDetail, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { RuleOutcomeChip, SeverityChip } from "@/components/ui/Badges";
import { Disclaimer, RuleId } from "@/components/ui/misc";

const CATS = ["FRAUD", "COMPLIANCE", "KYC", "DOCUMENT"] as const;
const RANK: Record<Severity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };

interface Finding {
  key: string;
  severity: Severity;
  title: string;
  detail: string;
  ruleId?: string;
  reference?: string | null;
  source: string;
}

export function FraudTab({ c }: { c: CaseDetail }) {
  const rules = c.decision.rules_fired.filter((r) => (CATS as readonly string[]).includes(r.category));
  const failing = rules.filter((r) => r.outcome === "FAIL" || r.outcome === "WARN");
  const passing = rules.filter((r) => r.outcome === "PASS");
  const findings: Finding[] = [
    ...failing.map((r, i) => ({
      key: `r-${r.rule_id}-${i}`,
      severity: r.severity,
      title: r.name,
      detail: r.detail,
      ruleId: r.rule_id,
      reference: r.reference,
      source: r.category,
    })),
    ...c.bundle.flags.map((f, i) => ({
      key: `f-${f.code}-${i}`,
      severity: f.severity,
      title: f.title,
      detail: f.detail,
      source: f.document_id ? `Document ${f.document_id}` : "Documents",
    })),
  ].sort((a, b) => RANK[a.severity] - RANK[b.severity]);

  const high = findings.filter((f) => f.severity === "CRITICAL" || f.severity === "HIGH").length;
  const med = findings.filter((f) => f.severity === "MEDIUM").length;
  const low = findings.filter((f) => f.severity === "LOW" || f.severity === "INFO").length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <Card className="md:col-span-5">
          <CardHeader title="Findings by severity" subtitle={`${rules.length} fraud, KYC, document and compliance checks run`} />
          <div className="grid grid-cols-3 gap-3">
            {[
              { n: high, label: "High", cls: "bg-bad-soft text-bad" },
              { n: med, label: "Medium", cls: "bg-warn-soft text-warn" },
              { n: low, label: "Low / info", cls: "bg-sage text-ink" },
            ].map((t) => (
              <div key={t.label} className={cn("flex aspect-square max-h-28 flex-col items-center justify-center rounded-surface", t.cls)}>
                <span className="font-display text-4xl font-semibold tnum">{t.n}</span>
                <span className="text-xs font-medium">{t.label}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-pewter">{findings.length} findings in total · {passing.length} checks passed</p>
        </Card>
        <Card className={cn("md:col-span-7", high ? "bg-bad-soft" : "bg-sage")}>
          <p className="text-sm font-medium text-graphite">Verdict</p>
          <p className="mt-2 font-display text-2xl font-semibold text-ink">
            {high ? `${high} high-severity signal${high > 1 ? "s" : ""} need investigation` : med ? "No high-severity signals; review the medium items" : "Clean: no fraud or compliance concerns"}
          </p>
          <p className="mt-2 text-sm text-graphite">
            Checks cover document tampering (PDF producer, edit dates, font anomalies), income inflation vs bank credits, round-number patterns, duplicate statements, high-risk merchants, negative list / PEP / sanctions, KYC completeness, CERSAI encumbrance, LAP end-use and valuation variance.
          </p>
        </Card>
      </div>

      <Card>
        <CardHeader title="Top findings" subtitle="Most severe first. Each links to its rule and regulatory basis." />
        {findings.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No findings">Every fraud, KYC and compliance check passed.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {findings.map((f) => (
              <li key={f.key} className="rounded-surface bg-fog p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityChip severity={f.severity} />
                  <span className="text-sm font-semibold text-ink">{f.title}</span>
                  {f.ruleId && <RuleId id={f.ruleId} className="ml-auto" />}
                </div>
                <p className="mt-1.5 text-[13px] text-graphite">{f.detail}</p>
                <p className="mt-1 truncate text-[11px] text-pewter" title={f.reference ?? undefined}>
                  {f.source}
                  {f.reference ? ` · ${f.reference}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {passing.length > 0 && (
        <Card>
          <CardHeader title="Checks passed" subtitle="Shown for completeness" display={false} />
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {passing.map((r, i) => (
              <li key={`${r.rule_id}-${i}`} className="flex items-start gap-2.5 rounded-surface border border-hairline px-3 py-2">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-ink">
                    {r.name} <RuleId id={r.rule_id} />
                  </p>
                  <p className="text-xs text-graphite">{r.detail}</p>
                </div>
                <RuleOutcomeChip outcome={r.outcome} />
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Disclaimer text="Checks point at things worth a look, not proof of fraud. Synthetic negative list." />
    </div>
  );
}
