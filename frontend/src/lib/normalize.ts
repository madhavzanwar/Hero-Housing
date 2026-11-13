/**
 * Normalisers for phase-2 endpoints whose JSON shapes are looser than the
 * typed contract (replay, queues, simulate). They accept the documented shape
 * and a few close variants so the UI never breaks on a renamed key.
 */
import type { CaseSummary, QueueGroup, QueueItem, ReplayResult, SimulateFlip, SimulateResult, SimulateSide } from "./types";
import { isRecord, num, str } from "./utils";

export const QUEUE_LABEL: Record<string, string> = {
  CREDIT: "Credit underwriting",
  FRAUD_RISK: "Fraud & risk",
  COMPLIANCE_KYC: "Compliance & KYC / AML",
  PROPERTY_LEGAL: "Property & legal",
};

export function normalizeReplay(raw: unknown, fallbackHash = ""): ReplayResult {
  const r = isRecord(raw) ? raw : {};
  const original = str(r.decision_hash) ?? str(r.original_hash) ?? str(r.expected_hash) ?? fallbackHash;
  const replay = str(r.replay_hash) ?? str(r.replayed_hash) ?? str(r.actual_hash) ?? str(r.new_hash) ?? "";
  const match = typeof r.match === "boolean" ? r.match : typeof r.matches === "boolean" ? r.matches : original !== "" && original === replay;
  return {
    match,
    decision_hash: original,
    replay_hash: replay,
    input_hash: str(r.input_hash),
    policy_hash: str(r.policy_hash),
    outcome: str(r.outcome) ?? str(r.replay_outcome),
    ms: num(r.ms) ?? num(r.duration_ms),
    note: str(r.note) ?? str(r.detail),
  };
}

function queueItem(raw: unknown): QueueItem | null {
  if (!isRecord(raw)) return null;
  const id = str(raw.id) ?? str(raw.case_id);
  if (!id) return null;
  return {
    id,
    applicant_name: str(raw.applicant_name) ?? str(raw.name) ?? id,
    outcome: (str(raw.outcome) as QueueItem["outcome"]) ?? null,
    product: (str(raw.product) as QueueItem["product"]) ?? null,
    loan_amount: num(raw.loan_amount) ?? null,
    sla_due_at: str(raw.sla_due_at) ?? null,
    reason: str(raw.reason) ?? str(raw.stp_reason) ?? str(raw.summary) ?? "",
    persona_id: str(raw.persona_id) ?? null,
  };
}

export function normalizeQueues(raw: unknown): QueueGroup[] {
  const out: QueueGroup[] = [];
  const push = (key: string, v: unknown) => {
    const g = isRecord(v) ? v : { items: v };
    const list = Array.isArray(g.items) ? g.items : Array.isArray(g.cases) ? g.cases : [];
    const q = str(g.queue) ?? str(g.name) ?? key;
    out.push({
      queue: q,
      label: str(g.label) ?? QUEUE_LABEL[q] ?? q,
      sla_hours: num(g.sla_hours),
      items: list.map(queueItem).filter((x): x is QueueItem => x !== null),
    });
  };
  if (Array.isArray(raw)) {
    // either a list of groups or a flat list of items with a `queue` key
    if (raw.every((x) => isRecord(x) && (Array.isArray(x.items) || Array.isArray(x.cases)))) raw.forEach((g, i) => push(String(i), g));
    else {
      const by: Record<string, unknown[]> = {};
      raw.forEach((x) => {
        const q = (isRecord(x) && str(x.queue)) || "CREDIT";
        (by[q] ??= []).push(x);
      });
      Object.entries(by).forEach(([k, v]) => push(k, { queue: k, items: v }));
    }
  } else if (isRecord(raw)) {
    const inner = raw.queues ?? raw;
    if (Array.isArray(inner)) return normalizeQueues(inner);
    if (isRecord(inner)) Object.entries(inner).forEach(([k, v]) => push(k, v));
  }
  return out;
}

function side(raw: unknown): SimulateSide {
  const r = isRecord(raw) ? raw : {};
  const by = isRecord(r.by_outcome) ? (Object.fromEntries(Object.entries(r.by_outcome).map(([k, v]) => [k, num(v) ?? 0])) as Record<string, number>) : undefined;
  return {
    approval_rate: num(r.approval_rate) ?? 0,
    expected_loss: num(r.expected_loss) ?? num(r.el) ?? 0,
    approved: num(r.approved) ?? 0,
    total: num(r.total) ?? num(r.total_cases) ?? 0,
    stp_rate: num(r.stp_rate),
    by_outcome: by,
  };
}

export function normalizeSimulate(raw: unknown): SimulateResult {
  const r = isRecord(raw) ? raw : {};
  const flips = (Array.isArray(r.flips) ? r.flips : Array.isArray(r.changes) ? r.changes : [])
    .filter(isRecord)
    .map(
      (f): SimulateFlip => ({
        case_id: str(f.case_id) ?? str(f.id) ?? "",
        applicant_name: str(f.applicant_name) ?? str(f.name) ?? "",
        from: str(f.from) ?? str(f.from_outcome) ?? str(f.before) ?? "",
        to: str(f.to) ?? str(f.to_outcome) ?? str(f.after) ?? "",
        reason: str(f.reason) ?? str(f.why) ?? "",
      }),
    );
  return { before: side(r.before ?? r.baseline), after: side(r.after ?? r.scenario), flips };
}

/** Offline fallback: build queues from case summaries + governance info. */
export function queuesFromCases(cases: { summary: CaseSummary; queue?: string | null; sla?: string | null; reason?: string }[]): QueueGroup[] {
  const by: Record<string, QueueItem[]> = {};
  for (const c of cases) {
    const q = c.queue ?? (c.summary.outcome === "REFER" ? "CREDIT" : null);
    if (!q) continue;
    (by[q] ??= []).push({
      id: c.summary.id,
      applicant_name: c.summary.applicant_name,
      outcome: c.summary.outcome,
      product: c.summary.product,
      loan_amount: c.summary.loan_amount,
      sla_due_at: c.sla ?? null,
      reason: c.reason ?? "",
      persona_id: c.summary.persona_id,
    });
  }
  return Object.entries(by).map(([q, items]) => ({ queue: q, label: QUEUE_LABEL[q] ?? q, items }));
}
