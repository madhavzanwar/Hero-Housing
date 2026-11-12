import type { DecisionOutcome, Severity } from "@/lib/types";
import type { Tone } from "./Chip";

export const OUTCOME_TONE: Record<DecisionOutcome, Tone> = {
  APPROVE: "lime",
  APPROVE_WITH_CONDITIONS: "warning",
  REFER: "info",
  DECLINE: "danger",
};

export const SEVERITY_TONE: Record<Severity, Tone> = {
  CRITICAL: "solid-danger",
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "success",
  INFO: "neutral",
};
