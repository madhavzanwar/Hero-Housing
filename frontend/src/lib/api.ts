import type {
  ApplicationForm,
  CaseDetail,
  CaseSummary,
  CopilotAnswer,
  DemoResetResponse,
  HealthResponse,
  ModelCard,
  OverrideRequest,
  PersonaDetail,
  PersonaInfo,
  PolicyDoc,
  PortfolioMetrics,
  QueueGroup,
  ReplayResult,
  SimulateRequest,
  SimulateResult,
  Kfs,
} from "./types";
import { normalizeQueues, normalizeReplay, normalizeSimulate } from "./normalize";
import { getMode, setMode } from "./mode";
import * as demo from "./demo";

const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Thrown when the backend cannot be reached at all (triggers demo mode). */
class OfflineError extends Error {}

function url(path: string): string {
  return `${BASE}/api${path}`;
}

async function detail(res: Response): Promise<string> {
  try {
    const text = await res.text();
    try {
      const body: unknown = JSON.parse(text);
      if (body && typeof body === "object" && "detail" in body) {
        const d = (body as { detail: unknown }).detail;
        return typeof d === "string" ? d : JSON.stringify(d);
      }
    } catch {
      /* not JSON */
    }
    return text.slice(0, 300) || res.statusText;
  } catch {
    return res.statusText;
  }
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(url(path), init);
  } catch (e) {
    throw new OfflineError(e instanceof Error ? e.message : "network error");
  }
  // Vite's dev proxy answers 502/504 (or an empty 500) when the backend is down.
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    throw new OfflineError(`backend unavailable (${res.status})`);
  }
  if (!res.ok) throw new ApiError(res.status, await detail(res));
  return res;
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await send(path, init);
  return (await res.json()) as T;
}

async function getText(path: string): Promise<string> {
  const res = await send(path);
  return res.text();
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return getJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

let probe: Promise<void> | null = null;

/** Decide live vs demo once, by probing /api/health (2.5 s timeout). */
export function ensureMode(): Promise<void> {
  if (getMode() !== "unknown") return Promise.resolve();
  probe ??= (async () => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2500);
    try {
      const res = await fetch(url("/health"), { signal: ctrl.signal });
      const body: unknown = res.ok ? await res.json() : null;
      if (body && typeof body === "object" && (body as { status?: unknown }).status === "ok") {
        setMode("live", "backend healthy");
      } else {
        setMode("demo", `health check returned ${res.status}`);
      }
    } catch {
      setMode("demo", "backend unreachable");
    } finally {
      clearTimeout(timer);
    }
  })();
  return probe;
}

/** Run the live call; if the backend is offline, switch to demo mode and serve the snapshot. */
async function withFallback<T>(live: () => Promise<T>, offline: () => Promise<T>): Promise<T> {
  await ensureMode();
  if (getMode() === "demo") return offline();
  try {
    return await live();
  } catch (e) {
    if (e instanceof OfflineError) {
      setMode("demo", e.message);
      return offline();
    }
    throw e;
  }
}

export const api = {
  health: () => getJson<HealthResponse>("/health"),

  personas: () => withFallback(() => getJson<PersonaInfo[]>("/personas"), demo.personas),
  persona: (id: string) => withFallback(() => getJson<PersonaDetail>(`/personas/${id}`), () => demo.persona(id)),

  /** Fetch one of a persona's synthetic documents as a File for the upload list. */
  personaFile: (id: string, name: string) =>
    withFallback(
      async () => {
        const res = await send(`/personas/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`);
        const blob = await res.blob();
        return new File([blob], name, { type: blob.type || guessMime(name) });
      },
      () => demo.personaFile(id, name),
    ),

  createCase: (form: ApplicationForm, files: File[], personaHint?: string) =>
    withFallback(
      () => {
        const fd = new FormData();
        fd.append("form", JSON.stringify(form));
        files.forEach((f) => fd.append("files", f, f.name));
        return getJson<CaseDetail>("/cases", { method: "POST", body: fd });
      },
      () => demo.createCase(form, files, personaHint),
    ),

  createCaseFromPersona: (personaId: string) =>
    withFallback(
      () => postJson<CaseDetail>(`/cases/from-persona/${personaId}`, {}),
      () => demo.createCase(null, [], personaId),
    ),

  listCases: () => withFallback(() => getJson<CaseSummary[]>("/cases"), demo.listCases),
  getCase: (id: string) => withFallback(() => getJson<CaseDetail>(`/cases/${id}`), () => demo.getCase(id)),

  documentUrl: (caseId: string, docId: string): string =>
    getMode() === "demo"
      ? demo.documentUrl(caseId, docId)
      : url(`/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docId)}`),

  override: (id: string, req: OverrideRequest) =>
    withFallback(() => postJson<CaseDetail>(`/cases/${id}/override`, req), () => demo.override(id, req)),

  copilot: (id: string, question: string) =>
    withFallback(
      () => postJson<CopilotAnswer>(`/cases/${id}/copilot`, { question }),
      () => demo.copilot(id, question),
    ),

  memo: (id: string) => withFallback(() => getText(`/cases/${id}/memo`), () => demo.memo(id)),
  sanctionLetter: (id: string) =>
    withFallback(() => getText(`/cases/${id}/sanction-letter`), () => demo.sanctionLetter(id)),

  portfolio: () => withFallback(() => getJson<PortfolioMetrics>("/portfolio"), demo.portfolio),
  policy: () => withFallback(() => getJson<PolicyDoc>("/policy"), demo.policy),
  modelCard: () => withFallback(() => getJson<ModelCard>("/model-card"), demo.modelCard),

  replay: (id: string) =>
    withFallback(async () => normalizeReplay(await postJson<unknown>(`/cases/${id}/replay`, {})), (): Promise<ReplayResult> => demo.replay(id)),

  queues: () => withFallback(async (): Promise<QueueGroup[]> => normalizeQueues(await getJson<unknown>("/queues")), demo.queues),

  simulate: (req: SimulateRequest) =>
    withFallback(async (): Promise<SimulateResult> => normalizeSimulate(await postJson<unknown>("/policy/simulate", req)), () => demo.simulate(req)),

  kfs: (id: string, lang: "en" | "hi") =>
    withFallback(
      async (): Promise<Kfs> => {
        const res = await send(`/cases/${id}/kfs?lang=${lang}`);
        const type = res.headers.get("content-type") ?? "";
        return type.includes("json") ? ((await res.json()) as Kfs) : res.text();
      },
      () => demo.kfs(id, lang),
    ),

  resetDemo: () =>
    withFallback(() => postJson<DemoResetResponse>("/demo/reset", {}), demo.reset),
};

export function guessMime(name: string): string {
  const n = name.toLowerCase();
  if (n.endsWith(".pdf")) return "application/pdf";
  if (n.endsWith(".png")) return "image/png";
  if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
  return "application/octet-stream";
}
