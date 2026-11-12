/**
 * Demo mode: serve everything from the static snapshot (src/demo/snapshot.json,
 * written by scripts/export_snapshot.mjs). Overrides are applied client-side and
 * kept in localStorage; Copilot falls back to a grounded client-side responder.
 */
import type {
  ApplicationForm,
  CaseDetail,
  CaseStatus,
  CaseSummary,
  CopilotAnswer,
  DemoResetResponse,
  DemoSnapshot,
  ModelCard,
  Override,
  OverrideRequest,
  PersonaDetail,
  PersonaInfo,
  PolicyDoc,
  PortfolioMetrics,
} from "./types";
import { answerOffline } from "./demoCopilot";

const OVERRIDES_KEY = "fphl:demo-overrides";

// import.meta.glob resolves to {} when the snapshot has not been generated yet.
const loaders = import.meta.glob<DemoSnapshot>("../demo/snapshot.json", { import: "default" });

const EMPTY: DemoSnapshot = {
  generated_at: "",
  cases: [],
  personas: [],
  portfolio: {
    total_cases: 0,
    by_outcome: {},
    by_product: {},
    approval_rate: 0,
    avg_turnaround_ms: 0,
    fraud_flagged: 0,
    avg_pd: 0,
    sanctioned_value: 0,
    override_rate: 0,
    grade_distribution: {},
    top_rules: [],
  },
  policy: { version: "unavailable", policy: {}, rules: {} },
  model_card: {},
};

let snapshotPromise: Promise<DemoSnapshot> | null = null;

export function loadSnapshot(): Promise<DemoSnapshot> {
  snapshotPromise ??= (async () => {
    const load = Object.values(loaders)[0];
    if (!load) return EMPTY;
    try {
      return await load();
    } catch {
      return EMPTY;
    }
  })();
  return snapshotPromise;
}

export async function hasSnapshot(): Promise<boolean> {
  return (await loadSnapshot()).cases.length > 0;
}

/* ---------------- client-side overrides ---------------- */

type OverrideStore = Record<string, Override[]>;

function readOverrides(): OverrideStore {
  try {
    const raw = localStorage.getItem(OVERRIDES_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? (parsed as OverrideStore) : {};
  } catch {
    return {};
  }
}

function writeOverrides(store: OverrideStore): void {
  try {
    localStorage.setItem(OVERRIDES_KEY, JSON.stringify(store));
  } catch {
    /* storage unavailable: overrides last for this page only */
  }
}

function applyOverrides(c: CaseDetail, list: Override[] | undefined): CaseDetail {
  if (!list || list.length === 0) return c;
  const last = list[list.length - 1];
  const decision = {
    ...c.decision,
    outcome: last.to_outcome,
    decided_by: last.underwriter,
    decided_at: last.at,
    sanctioned_amount: last.sanctioned_amount ?? c.decision.sanctioned_amount,
  };
  const audit = [
    ...c.audit,
    ...list.map((o) => ({
      at: o.at,
      actor: `underwriter:${o.underwriter}`,
      action: "OVERRIDE",
      detail: `${o.from_outcome} → ${o.to_outcome}: ${o.reason}`,
      data: { offline_demo: true },
      hash: "",
    })),
  ];
  return { ...c, decision, overrides: [...c.overrides, ...list], audit, status: "OVERRIDDEN" as CaseStatus };
}

function summarize(c: CaseDetail): CaseSummary {
  const fraudFails = c.decision.rules_fired.filter((r) => r.category === "FRAUD" && r.outcome === "FAIL").length;
  return {
    id: c.id,
    applicant_name: c.applicant.name,
    product: c.form.product,
    loan_amount: c.form.loan_amount,
    property_value: c.form.property_value,
    status: c.status,
    outcome: c.decision.outcome,
    pd: c.risk.pd,
    grade: c.risk.grade,
    flags: c.bundle.flags.length + fraudFails,
    created_at: c.created_at,
    turnaround_ms: c.decision.turnaround_ms,
    persona_id: c.persona_id,
    segment: null,
  };
}

async function allCases(): Promise<CaseDetail[]> {
  const snap = await loadSnapshot();
  const ov = readOverrides();
  return snap.cases.map((c) => applyOverrides(c, ov[c.id]));
}

function notFound(what: string): Error {
  return new Error(`${what} is not in the offline demo snapshot`);
}

/* ---------------- API surface (mirrors lib/api.ts) ---------------- */

export async function personas(): Promise<PersonaInfo[]> {
  const snap = await loadSnapshot();
  return snap.personas.map((p) => ({ ...p, case_id: snap.cases.find((c) => c.persona_id === p.id)?.id ?? p.case_id }));
}

export async function persona(id: string): Promise<PersonaDetail> {
  const snap = await loadSnapshot();
  const detail = snap.persona_details?.find((p) => p.id === id);
  if (detail) return detail;
  const info = snap.personas.find((p) => p.id === id);
  const c = snap.cases.find((x) => x.persona_id === id);
  if (!info || !c) throw notFound(`Persona ${id}`);
  return { ...info, form: c.form, expected: {} };
}

export async function personaFile(id: string, name: string): Promise<File> {
  const snap = await loadSnapshot();
  const c = snap.cases.find((x) => x.persona_id === id);
  const doc = c?.bundle.documents.find((d) => d.filename === name);
  if (c && doc) {
    try {
      const res = await fetch(documentUrl(c.id, doc.id));
      if (res.ok) {
        const blob = await res.blob();
        return new File([blob], name, { type: doc.mime_type });
      }
    } catch {
      /* fall through to a placeholder */
    }
  }
  // The offline engine does not read bytes; a named placeholder is enough to map to the persona.
  return new File([`offline demo placeholder for ${name}`], name, { type: "text/plain" });
}

/** "Run underwriting" offline: map the upload to the matching persona's precomputed case. */
export async function createCase(form: ApplicationForm | null, files: File[], personaHint?: string): Promise<CaseDetail> {
  const cases = await allCases();
  const snap = await loadSnapshot();
  let match = personaHint ? cases.find((c) => c.persona_id === personaHint) : undefined;
  if (!match && files.length) {
    const names = new Set(files.map((f) => f.name));
    let best = 0;
    for (const p of snap.personas) {
      const overlap = p.files.filter((f) => names.has(f)).length;
      const c = cases.find((x) => x.persona_id === p.id);
      const nameHit = form && c && c.form.applicant_name === form.applicant_name ? 100 : 0;
      if (c && overlap + nameHit > best) {
        best = overlap + nameHit;
        match = c;
      }
    }
  }
  if (!match && form) match = cases.find((c) => c.form.applicant_name.toLowerCase() === form.applicant_name.toLowerCase());
  if (!match) {
    throw new Error("Offline demo mode can only underwrite the 12 preloaded personas. Pick a persona chip and load its documents.");
  }
  return match;
}

export async function listCases(): Promise<CaseSummary[]> {
  return (await allCases()).map(summarize);
}

export async function getCase(id: string): Promise<CaseDetail> {
  const c = (await allCases()).find((x) => x.id === id);
  if (!c) throw notFound(`Case ${id}`);
  return c;
}

export function documentUrl(caseId: string, docId: string): string {
  return `${import.meta.env.BASE_URL}demo-docs/${encodeURIComponent(caseId)}/${encodeURIComponent(docId)}`;
}

export async function override(id: string, req: OverrideRequest): Promise<CaseDetail> {
  const base = await getCase(id);
  const entry: Override = {
    at: new Date().toISOString(),
    underwriter: req.underwriter,
    from_outcome: base.decision.outcome,
    to_outcome: req.to_outcome,
    reason: req.reason,
    sanctioned_amount: req.sanctioned_amount ?? null,
  };
  const store = readOverrides();
  store[id] = [...(store[id] ?? []), entry];
  writeOverrides(store);
  return getCase(id);
}

export async function copilot(id: string, question: string): Promise<CopilotAnswer> {
  return answerOffline(await getCase(id), question);
}

export async function memo(id: string): Promise<string> {
  const snap = await loadSnapshot();
  return snap.memos?.[id] ?? (await getCase(id)).memo_markdown;
}

export async function sanctionLetter(id: string): Promise<string> {
  const snap = await loadSnapshot();
  const letter = snap.letters?.[id];
  if (letter) return letter;
  const c = await getCase(id);
  return `# Outcome letter — ${c.id}\n\n> The outcome letter is not part of the offline snapshot. Decision: **${c.decision.outcome}**.\n`;
}

export async function portfolio(): Promise<PortfolioMetrics> {
  const snap = await loadSnapshot();
  const cases = await allCases();
  const n = cases.length;
  const overridden = cases.filter((c) => c.overrides.length > 0).length;
  const byOutcome: Record<string, number> = { APPROVE: 0, APPROVE_WITH_CONDITIONS: 0, REFER: 0, DECLINE: 0 };
  cases.forEach((c) => {
    byOutcome[c.decision.outcome] = (byOutcome[c.decision.outcome] ?? 0) + 1;
  });
  const approved = cases.filter((c) => c.decision.outcome === "APPROVE" || c.decision.outcome === "APPROVE_WITH_CONDITIONS");
  return {
    ...snap.portfolio,
    by_outcome: n ? byOutcome : snap.portfolio.by_outcome,
    approval_rate: n ? approved.length / n : snap.portfolio.approval_rate,
    override_rate: n ? overridden / n : snap.portfolio.override_rate,
  };
}

export async function policy(): Promise<PolicyDoc> {
  return (await loadSnapshot()).policy;
}

export async function modelCard(): Promise<ModelCard> {
  return (await loadSnapshot()).model_card;
}

export async function reset(): Promise<DemoResetResponse> {
  writeOverrides({});
  const snap = await loadSnapshot();
  return { cases: snap.cases.length, errors: [], ms: 0 };
}
