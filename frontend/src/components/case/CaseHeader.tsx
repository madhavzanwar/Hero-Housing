import { FileSignature, FileText, Sparkles } from "lucide-react";
import type { CaseDetail } from "@/lib/types";
import { dateTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { StatusChip } from "@/components/ui/Badges";
import { Avatar, Mono } from "@/components/ui/misc";

export function CaseHeader({ c, onTab }: { c: CaseDetail; onTab: (tab: string) => void }) {
  const a = c.applicant;
  return (
    <Card className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-start gap-4">
        <Avatar name={a.name} className="size-12 text-sm" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-[26px] font-medium leading-tight text-ink sm:text-[28px]">{a.name}</h1>
            <StatusChip status={c.status} testId="case-status" />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Chip tone={c.form.product === "LAP" ? "cyan" : "outline"}>{c.form.product === "LAP" ? "Loan against property" : "Home loan"}</Chip>
            {(a.city ?? c.form.city) && <Chip tone="outline">{a.city ?? c.form.city}</Chip>}
            <Chip tone="outline">{a.employment_type === "SALARIED" ? "Salaried" : "Self-employed"}</Chip>
            {a.employer_or_business && <Chip tone="neutral" className="max-w-[240px] truncate">{a.employer_or_business}</Chip>}
            {c.form.co_applicant && <Chip tone="info">Co-applicant: {c.form.co_applicant.name}</Chip>}
          </div>
          <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-pewter">
            <span>
              Case <Mono className="text-graphite">{c.id}</Mono>
            </span>
            {a.pan_masked && (
              <span>
                PAN <Mono className="text-graphite">{a.pan_masked}</Mono>
              </span>
            )}
            {a.aadhaar_masked && (
              <span>
                Aadhaar <Mono className="text-graphite">{a.aadhaar_masked}</Mono>
              </span>
            )}
            <span>Age {a.age ? a.age.toFixed(1) : "—"}</span>
            <span>Created {dateTime(c.created_at)}</span>
            <span>Policy {c.decision.policy_version}</span>
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => onTab("memo")}>
          <FileText className="size-4" aria-hidden /> Credit memo
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onTab("memo:letter")}>
          <FileSignature className="size-4" aria-hidden /> Outcome letter
        </Button>
        <Button variant="lime" size="sm" onClick={() => window.dispatchEvent(new CustomEvent("fphl:open-copilot"))}>
          <Sparkles className="size-4" aria-hidden /> Ask Copilot
        </Button>
      </div>
    </Card>
  );
}
