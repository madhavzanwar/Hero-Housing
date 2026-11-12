import { FileImage, FileText, FolderDown, Loader2, Play, Trash2, UploadCloud, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { inrShort } from "@/lib/format";
import { DOC_LABEL, PIPELINE_NODES } from "@/lib/labels";
import { personaTag } from "@/lib/personas";
import type { ApplicationForm, DocType, PersonaInfo, TraceStep } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { SelectField, TextField } from "@/components/ui/Field";
import { Disclaimer, PageHeader } from "@/components/ui/misc";
import { AgentGraph, type GraphStep } from "@/components/case/AgentGraph";

const EMPTY_FORM: ApplicationForm = {
  product: "HOME_LOAN",
  applicant_name: "",
  dob: null,
  gender: null,
  city: "",
  employment_type: "SALARIED",
  employer_or_business: "",
  years_in_job: 3,
  declared_monthly_income: 0,
  existing_emi: 0,
  bureau_score: null,
  loan_amount: 0,
  tenure_months: 240,
  property_value: 0,
  property_type: "RESIDENTIAL",
  property_city: "",
  purpose: "Purchase of residential flat",
  lap_end_use: null,
  co_applicant: null,
  is_first_home: true,
  rate_type: "FLOATING",
};

/** Filename heuristic for the upload list (the backend classifies for real). */
function guessDocType(name: string): { type: DocType; confidence: number } {
  const n = name.toLowerCase();
  const rules: [RegExp, DocType][] = [
    [/pan/, "PAN"],
    [/aadh?aar/, "AADHAAR"],
    [/salary|payslip|pay_slip/, "SALARY_SLIP"],
    [/form.?16/, "FORM16"],
    [/itr|tax.?return/, "ITR"],
    [/bank|statement/, "BANK_STATEMENT"],
    [/deed|agreement|sale|title/, "SALE_DEED"],
    [/valuation|valuer/, "VALUATION_REPORT"],
  ];
  for (const [re, t] of rules) if (re.test(n)) return { type: t, confidence: 0.82 };
  return { type: "UNKNOWN", confidence: 0.3 };
}

function sizeLabel(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${Math.round(b / 1024)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-pewter">{title}</legend>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>
    </fieldset>
  );
}

function numberInput(v: number | null | undefined): string {
  return v == null || v === 0 ? "" : String(v);
}

export default function NewCase() {
  const navigate = useNavigate();
  const personas = useAsync(() => api.personas(), "personas");
  const [form, setForm] = useState<ApplicationForm>(EMPTY_FORM);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [steps, setSteps] = useState<GraphStep[] | null>(null);
  const [running, setRunning] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<number | null>(null);
  const traceRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);

  function set<K extends keyof ApplicationForm>(key: K, value: ApplicationForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function quickFill(p: PersonaInfo) {
    setPersonaId(p.id);
    setFiles([]);
    try {
      const d = await api.persona(p.id);
      setForm({ ...EMPTY_FORM, ...d.form });
      toast.success(`Form filled from ${p.applicant_name} (${p.id})`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load persona");
    }
  }

  async function loadPersonaDocs() {
    const p = personas.data?.find((x) => x.id === personaId);
    if (!p) return;
    setLoadingDocs(true);
    try {
      const loaded = await Promise.all(p.files.map((name) => api.personaFile(p.id, name)));
      setFiles((prev) => [...prev.filter((f) => !p.files.includes(f.name)), ...loaded]);
      toast.success(`${loaded.length} documents added`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load documents");
    } finally {
      setLoadingDocs(false);
    }
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    const incoming = Array.from(list);
    setFiles((prev) => [...prev.filter((f) => !incoming.some((n) => n.name === f.name)), ...incoming]);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }

  async function run() {
    if (!form.applicant_name.trim() || form.loan_amount <= 0 || form.property_value <= 0 || form.declared_monthly_income <= 0) {
      toast.error("Fill applicant name, income, loan amount and property value (or pick a persona).");
      return;
    }
    setRunning(true);
    let i = 0;
    setSteps(PIPELINE_NODES.map((node, k) => ({ node, state: k === 0 ? "running" : "waiting" })));
    // Animate node by node while the engine runs; real timings replace these on completion.
    timer.current = window.setInterval(() => {
      i = Math.min(i + 1, PIPELINE_NODES.length - 1);
      setSteps(PIPELINE_NODES.map((node, k) => ({ node, state: k < i ? "done" : k === i ? "running" : "waiting" })));
    }, 650);
    window.setTimeout(() => traceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    try {
      const c = await api.createCase(form, files, personaId ?? undefined);
      if (timer.current) window.clearInterval(timer.current);
      const trace: TraceStep[] = c.copilot_trace.length ? c.copilot_trace : PIPELINE_NODES.map((node) => ({ node, ms: 0, summary: "", status: "ok" }));
      // Reveal the real trace quickly, one node at a time.
      for (let k = 1; k <= trace.length; k++) {
        setSteps(trace.map((t, j) => ({ node: t.node, ms: t.ms, summary: t.summary, state: j < k ? "done" : "waiting" })));
        await new Promise((r) => setTimeout(r, 70));
      }
      toast.success(`Case ${c.id} underwritten`);
      await new Promise((r) => setTimeout(r, 450));
      navigate(`/cases/${c.id}`);
    } catch (e) {
      if (timer.current) window.clearInterval(timer.current);
      setSteps((s) => s?.map((x) => (x.state === "running" ? { ...x, state: "error" } : x)) ?? null);
      toast.error(e instanceof Error ? e.message : "Underwriting failed");
      setRunning(false);
    }
  }

  const selected = personas.data?.find((p) => p.id === personaId);
  const isLap = form.product === "LAP";

  return (
    <div className="space-y-4">
      <PageHeader
        title="New underwriting case"
        subtitle="Capture the application, attach the applicant's documents and let the engine read, check and decide. Pick a persona to fill everything in one click."
      />

      <Card>
        <CardHeader title="Persona quick-fill" subtitle="12 synthetic applicants covering clean, conditional, referral, fraud and decline paths" />
        <div className="flex flex-wrap gap-2" role="group" aria-label="Persona quick-fill">
          {(personas.data ?? []).map((p) => {
            const tag = personaTag(p);
            const active = p.id === personaId;
            return (
              <button
                key={p.id}
                type="button"
                data-testid={`persona-chip-${p.id}`}
                aria-pressed={active}
                onClick={() => void quickFill(p)}
                title={p.title ?? undefined}
                className={cn(
                  "flex min-h-10 items-center gap-2 rounded-full border px-3 text-[13px] transition-colors",
                  active ? "border-lime-dark bg-lime text-on-lime" : "border-mist bg-paper text-ink hover:border-lime-dark",
                )}
              >
                <span className={cn("font-mono text-[11px]", active ? "text-on-lime/70" : "text-pewter")}>{p.id}</span>
                <span className="font-medium">{p.applicant_name.split(" ")[0]}</span>
                <span className={cn("text-[11px]", active ? "text-on-lime/70" : "text-pewter")}>
                  {p.product === "LAP" ? "LAP" : "HL"} {inrShort(p.loan_amount)}
                </span>
                {!active && (
                  <Chip tone={tag.tone} className="px-1.5 py-0 text-[10px]">
                    {tag.text}
                  </Chip>
                )}
              </button>
            );
          })}
          {personas.loading && <Loader2 className="size-5 animate-spin text-pewter" aria-label="Loading personas" />}
        </div>
        {selected?.description && <p className="mt-3 max-w-3xl text-[13px] text-graphite">{selected.description}</p>}
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card className="xl:col-span-8">
          <CardHeader title="Application" subtitle="What the RM declares at intake, before any document is read" />
          <div className="space-y-6">
            <Section title="Applicant">
              <TextField label="Applicant name" value={form.applicant_name} onChange={(e) => set("applicant_name", e.target.value)} required wrapClassName="sm:col-span-2" />
              <TextField label="Date of birth" type="date" value={form.dob ?? ""} onChange={(e) => set("dob", e.target.value || null)} />
              <SelectField
                label="Gender"
                value={form.gender ?? ""}
                onChange={(e) => set("gender", (e.target.value || null) as ApplicationForm["gender"])}
                options={[
                  { value: "", label: "Not stated" },
                  { value: "F", label: "Female" },
                  { value: "M", label: "Male" },
                  { value: "O", label: "Other" },
                ]}
              />
              <SelectField
                label="Employment"
                value={form.employment_type}
                onChange={(e) => set("employment_type", e.target.value as ApplicationForm["employment_type"])}
                options={[
                  { value: "SALARIED", label: "Salaried" },
                  { value: "SELF_EMPLOYED", label: "Self-employed" },
                ]}
              />
              <TextField label="Employer / business" value={form.employer_or_business ?? ""} onChange={(e) => set("employer_or_business", e.target.value)} wrapClassName="sm:col-span-2" />
              <TextField label="Years in job / business" type="number" min={0} step={0.1} value={numberInput(form.years_in_job)} onChange={(e) => set("years_in_job", Number(e.target.value))} />
              <TextField label="City" value={form.city ?? ""} onChange={(e) => set("city", e.target.value)} />
              <TextField label="Net monthly income (₹)" type="number" min={0} inputMode="numeric" value={numberInput(form.declared_monthly_income)} onChange={(e) => set("declared_monthly_income", Number(e.target.value))} required />
              <TextField label="Existing EMIs / month (₹)" type="number" min={0} inputMode="numeric" value={numberInput(form.existing_emi)} onChange={(e) => set("existing_emi", Number(e.target.value))} />
              <TextField label="Bureau score" type="number" min={300} max={900} value={numberInput(form.bureau_score)} onChange={(e) => set("bureau_score", e.target.value ? Number(e.target.value) : null)} hint="Synthetic bureau pull" />
            </Section>

            <Section title="Loan & property">
              <SelectField
                label="Product"
                value={form.product}
                onChange={(e) => set("product", e.target.value as ApplicationForm["product"])}
                options={[
                  { value: "HOME_LOAN", label: "Home loan" },
                  { value: "LAP", label: "Loan against property" },
                ]}
              />
              <TextField label="Loan amount (₹)" type="number" min={0} inputMode="numeric" value={numberInput(form.loan_amount)} onChange={(e) => set("loan_amount", Number(e.target.value))} required hint={form.loan_amount ? inrShort(form.loan_amount) : undefined} />
              <TextField label="Tenure (months)" type="number" min={12} max={360} value={numberInput(form.tenure_months)} onChange={(e) => set("tenure_months", Number(e.target.value))} />
              <SelectField
                label="Rate type"
                value={form.rate_type}
                onChange={(e) => set("rate_type", e.target.value as ApplicationForm["rate_type"])}
                options={[
                  { value: "FLOATING", label: "Floating" },
                  { value: "FIXED", label: "Fixed" },
                ]}
              />
              <TextField label="Property value (₹)" type="number" min={0} inputMode="numeric" value={numberInput(form.property_value)} onChange={(e) => set("property_value", Number(e.target.value))} required hint={form.property_value ? inrShort(form.property_value) : undefined} />
              <SelectField
                label="Property type"
                value={form.property_type}
                onChange={(e) => set("property_type", e.target.value as ApplicationForm["property_type"])}
                options={[
                  { value: "RESIDENTIAL", label: "Residential" },
                  { value: "COMMERCIAL", label: "Commercial" },
                  { value: "PLOT", label: "Plot" },
                ]}
              />
              <TextField label="Property city" value={form.property_city ?? ""} onChange={(e) => set("property_city", e.target.value)} />
              <TextField label="Purpose" value={form.purpose} onChange={(e) => set("purpose", e.target.value)} />
              {isLap && <TextField label="LAP end use" value={form.lap_end_use ?? ""} onChange={(e) => set("lap_end_use", e.target.value || null)} wrapClassName="sm:col-span-2" hint="Checked against allowed / prohibited end uses" />}
            </Section>

            <Section title="Co-applicant (optional)">
              <TextField
                label="Co-applicant name"
                value={form.co_applicant?.name ?? ""}
                onChange={(e) =>
                  set("co_applicant", e.target.value ? { relation: "Spouse", monthly_net_income: 0, existing_emi: 0, ...form.co_applicant, name: e.target.value } : null)
                }
              />
              <TextField label="Relation" value={form.co_applicant?.relation ?? ""} disabled={!form.co_applicant} onChange={(e) => form.co_applicant && set("co_applicant", { ...form.co_applicant, relation: e.target.value })} />
              <TextField label="Co-applicant income (₹)" type="number" min={0} disabled={!form.co_applicant} value={numberInput(form.co_applicant?.monthly_net_income)} onChange={(e) => form.co_applicant && set("co_applicant", { ...form.co_applicant, monthly_net_income: Number(e.target.value) })} />
              <TextField label="Co-applicant EMIs (₹)" type="number" min={0} disabled={!form.co_applicant} value={numberInput(form.co_applicant?.existing_emi)} onChange={(e) => form.co_applicant && set("co_applicant", { ...form.co_applicant, existing_emi: Number(e.target.value) })} />
            </Section>
          </div>
        </Card>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Card>
            <CardHeader title="Documents" subtitle="PAN, Aadhaar, salary slips / ITR, Form 16, bank statement, sale deed, valuation" />
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "flex flex-col items-center justify-center gap-3 rounded-surface border-2 border-dashed px-4 py-7 text-center transition-colors",
                dragging ? "border-lime-dark bg-tint-lime" : "border-mist bg-fog",
              )}
            >
              <span className="flex size-11 items-center justify-center rounded-full bg-paper text-olive shadow-sm">
                <UploadCloud className="size-5" aria-hidden />
              </span>
              <p className="text-sm font-semibold text-ink">Drop files here</p>
              <div className="flex flex-wrap justify-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => inputRef.current?.click()}>
                  Choose files
                </Button>
                <Button size="sm" variant="secondary" data-testid="load-persona-docs" disabled={!personaId || loadingDocs} onClick={() => void loadPersonaDocs()} title={personaId ? undefined : "Pick a persona first"}>
                  {loadingDocs ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <FolderDown className="size-3.5" aria-hidden />}
                  Load persona documents
                </Button>
              </div>
              <input ref={inputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg" className="sr-only" aria-label="Choose documents" onChange={(e) => addFiles(e.target.files)} />
              <p className="text-[11px] text-pewter">PDF (text layer) or PNG/JPG (OCR) · up to 15 MB each · PII is masked on read</p>
            </div>

            <ul data-testid="file-list" aria-label="Files to upload" className="mt-3 space-y-1.5">
              {files.map((f) => {
                const g = guessDocType(f.name);
                const Icon = f.name.toLowerCase().endsWith(".pdf") ? FileText : FileImage;
                return (
                  <li key={f.name} className="flex items-center gap-2.5 rounded-surface bg-fog px-3 py-2">
                    <Icon className="size-4 shrink-0 text-graphite" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-ink">{f.name}</p>
                      <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-pewter">
                        {DOC_LABEL[g.type]} · {sizeLabel(f.size)}
                      </p>
                    </div>
                    <ConfidenceChip value={g.confidence} label="" className="hidden sm:inline-flex" />
                    <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles((x) => x.filter((y) => y !== f))} className="rounded-full p-1.5 text-pewter hover:bg-paper hover:text-bad">
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
            {files.length === 0 && <p className="mt-3 text-center text-xs text-pewter">No files yet. Missing documents become conditions, not silent failures.</p>}
          </Card>

          <Card className="bg-sage">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-paper text-ink">
                <UserRound className="size-4" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-semibold text-ink">{form.applicant_name || "No applicant yet"}</p>
                <p className="text-[13px] text-graphite">
                  {form.product === "LAP" ? "LAP" : "Home loan"} · {inrShort(form.loan_amount)} on {inrShort(form.property_value)} · {files.length} document{files.length === 1 ? "" : "s"}
                </p>
              </div>
            </div>
            <Button variant="lime" size="lg" className="mt-4 w-full" data-testid="run-underwriting" disabled={running} onClick={() => void run()}>
              {running ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
              {running ? "Underwriting…" : "Run underwriting"}
            </Button>
            <p className="mt-2 text-center text-[11px] text-graphite">Reads documents, runs 40+ policy rules, the PD model and a 1,000-path Monte Carlo.</p>
          </Card>
        </div>
      </div>

      {steps && (
        <Card ref={traceRef} className="scroll-mt-20">
          <CardHeader title="Underwriting Copilot at work" subtitle="LangGraph agent trace: each node reads the case file, adds evidence and hands over" />
          <AgentGraph steps={steps} centerTitle={form.applicant_name || "Case file"} centerText={`${files.length} documents · ${form.product === "LAP" ? "LAP" : "HL"} ${inrShort(form.loan_amount)}`} />
        </Card>
      )}
      <Disclaimer />
    </div>
  );
}
