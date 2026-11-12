import { CheckCircle2, CircleAlert, CircleHelp, Info, XCircle } from "lucide-react";
import type { CaseStatus, DecisionOutcome, RuleOutcome, Severity } from "@/lib/types";
import { OUTCOME_LABEL, RULE_OUTCOME_LABEL, SEVERITY_LABEL, STATUS_LABEL } from "@/lib/labels";
import { Chip, type Tone } from "./Chip";
import { OUTCOME_TONE, SEVERITY_TONE } from "./tones";


export function OutcomeChip({ outcome, short = false }: { outcome: DecisionOutcome | null | undefined; short?: boolean }) {
  if (!outcome) return <Chip tone="neutral">Pending</Chip>;
  const label = short
    ? { APPROVE: "Approved", APPROVE_WITH_CONDITIONS: "Conditions", REFER: "Refer", DECLINE: "Declined" }[outcome]
    : OUTCOME_LABEL[outcome];
  return (
    <Chip tone={OUTCOME_TONE[outcome]} dot>
      {label}
    </Chip>
  );
}

const STATUS_TONE: Record<CaseStatus, Tone> = {
  PROCESSING: "neutral",
  AWAITING_DOCUMENTS: "warning",
  DECIDED: "success",
  IN_REVIEW: "info",
  OVERRIDDEN: "accent",
  SANCTIONED: "lime",
};

export function StatusChip({ status, testId }: { status: CaseStatus; testId?: string }) {
  return (
    <Chip tone={STATUS_TONE[status]} data-testid={testId}>
      {STATUS_LABEL[status]}
    </Chip>
  );
}


export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <Chip tone={SEVERITY_TONE[severity]} className="uppercase tracking-wide text-[10px] font-semibold">
      {SEVERITY_LABEL[severity]}
    </Chip>
  );
}

const RULE_TONE: Record<RuleOutcome, Tone> = { PASS: "success", WARN: "warning", FAIL: "danger", INFO: "neutral" };
const RULE_ICON = { PASS: CheckCircle2, WARN: CircleAlert, FAIL: XCircle, INFO: Info } as const;

export function RuleOutcomeChip({ outcome }: { outcome: RuleOutcome }) {
  const Icon = RULE_ICON[outcome] ?? CircleHelp;
  return (
    <Chip tone={RULE_TONE[outcome]}>
      <Icon className="size-3" aria-hidden />
      {RULE_OUTCOME_LABEL[outcome]}
    </Chip>
  );
}

export function GradeChip({ grade, band }: { grade: string | null | undefined; band?: string }) {
  if (!grade) return <Chip>—</Chip>;
  const tone: Tone = grade === "A" ? "success" : grade === "B" ? "cyan" : grade === "C" ? "warning" : "danger";
  return (
    <Chip tone={tone}>
      Grade {grade}
      {band ? ` · ${band}` : ""}
    </Chip>
  );
}
