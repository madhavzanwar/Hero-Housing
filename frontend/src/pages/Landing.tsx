import { ArrowRight, Calculator, Check, ScanText, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { inrShort } from "@/lib/format";
import { personaTag } from "@/lib/personas";
import type { PersonaInfo } from "@/lib/types";
import { ButtonLink } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Avatar, Disclaimer } from "@/components/ui/misc";
import { ThemeToggle } from "@/components/layout/AppShell";
import { Wordmark } from "@/components/layout/Logo";

const FEATURES = [
  { icon: ScanText, tag: "Evidence", title: "Document AI", text: "Classifies PAN, Aadhaar, slips, Form 16, ITR, statements, deeds and valuations; OCR with confidence; tamper checks on PDF metadata and fonts." },
  { icon: Calculator, tag: "Assessment", title: "Eligibility engine", text: "FOIR, LTV slabs, age-at-maturity and tenure from a versioned YAML policy. Every number carries its rule ID and RBI citation." },
  { icon: Wand2, tag: "Assessment", title: "Explainable risk", text: "Calibrated LightGBM PD with SHAP reasons in plain English, plus a FinPilot 1,000-path Monte Carlo of the buffer after EMI." },
  { icon: Sparkles, tag: "Decision", title: "Underwriting Copilot", text: "A LangGraph agent that runs the checks, drafts the credit memo and sanction letter, and answers questions with citations." },
];

function PersonaCard({ p }: { p: PersonaInfo }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const tag = personaTag(p);
  async function open() {
    setBusy(true);
    try {
      const id = p.case_id ?? (await api.createCaseFromPersona(p.id)).id;
      navigate(`/cases/${id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load case");
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col rounded-card bg-surface p-5 elevation-card elevation-card-hover">
      <div className="flex items-start gap-3">
        <Avatar name={p.applicant_name} className="size-10" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-ink">{p.applicant_name}</p>
          <p className="text-xs text-pewter">
            {p.city} · {p.product === "LAP" ? "LAP" : "Home loan"} {inrShort(p.loan_amount)}
          </p>
        </div>
        <Chip tone={tag.tone} className="text-[11px]">
          {tag.text}
        </Chip>
      </div>
      <p className="mt-3 line-clamp-3 flex-1 text-[13px] text-graphite">{p.description ?? p.title}</p>
      <button type="button" onClick={() => void open()} disabled={busy} className="mt-4 inline-flex items-center gap-1 self-start text-sm font-semibold text-ink hover:underline disabled:opacity-50">
        {busy ? "Underwriting…" : "Load case"} <ArrowRight className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

export default function Landing() {
  const personas = useAsync(() => api.personas(), "personas");
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-hairline bg-background/75 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
          <Link to="/" aria-label="FinPilot HomeLoan home">
            <Wordmark />
          </Link>
          <nav className="ml-auto flex items-center gap-1 text-sm" aria-label="Site">
            <Link to="/pipeline" className="hidden rounded-full px-3 py-1.5 text-graphite hover:text-ink sm:block" data-testid="nav-pipeline">
              Pipeline
            </Link>
            <Link to="/copilot" className="hidden rounded-full px-3 py-1.5 text-graphite hover:text-ink sm:block">
              Copilot
            </Link>
            <ThemeToggle />
            <ButtonLink to="/pipeline" variant="lime" size="sm" className="rounded-full">
              Open app
            </ButtonLink>
          </nav>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div aria-hidden className="landing-grid absolute inset-0" />
        <div className="relative mx-auto max-w-5xl px-4 pb-20 pt-16 text-center sm:pt-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-hairline bg-paper px-3 py-1 text-xs font-medium text-graphite shadow-sm">
            <span className="size-1.5 rounded-full bg-leaf" aria-hidden /> Hero Housing Fintech Challenge · PS2 · Digitally automated mortgage underwriting
          </span>
          <h1 className="mt-6 font-display text-[44px] font-medium leading-[1.02] text-ink sm:text-[64px] lg:text-[72px]">
            Home-loan underwriting, <em className="font-medium text-ember">explained</em> — in minutes.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-graphite sm:text-lg">
            Upload the applicant's documents. FinPilot HomeLoan reads them, checks them against each other and the bank statement, applies your credit policy and a calibrated risk model, and hands the underwriter a decision with every reason cited.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <ButtonLink to="/pipeline" variant="lime" size="lg">
              Open the pipeline <ArrowRight className="size-4" aria-hidden />
            </ButtonLink>
            <ButtonLink to="/cases/new" variant="white" size="lg">
              Try a persona
            </ButtonLink>
          </div>
          <ul className="mt-6 flex flex-wrap justify-center gap-2">
            {["Rules + ML hybrid", "Works offline — no paid keys", "RBI LTV caps cited", "Human override with audit trail"].map((t) => (
              <li key={t} className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-paper px-3 py-1 text-xs text-graphite">
                <Check className="size-3 text-ok" aria-hidden /> {t}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-16">
        <h2 className="text-center font-display text-3xl font-medium text-ink sm:text-4xl">Engineered for the underwriter's desk</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-graphite">Three lanes, never blurred: evidence → assessment → decision and conditions.</p>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f, i) => (
            <div key={f.title} className={`rounded-card p-6 ${i === 3 ? "border border-lime-dark/50 bg-lime text-on-lime" : "bg-surface elevation-card"}`}>
              <span className={`flex size-10 items-center justify-center rounded-full ${i === 3 ? "bg-white/60" : "bg-sage text-ink"}`}>
                <f.icon className="size-5" strokeWidth={1.75} aria-hidden />
              </span>
              <p className={`mt-4 text-[11px] font-semibold uppercase tracking-wider ${i === 3 ? "text-on-lime/70" : "text-pewter"}`}>{f.tag}</p>
              <p className="mt-1 font-display text-xl font-medium">{f.title}</p>
              <p className={`mt-2 text-sm ${i === 3 ? "text-on-lime/80" : "text-graphite"}`}>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-16">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-3xl font-medium text-ink">Test drive on 12 curated personas</h2>
            <p className="mt-1 text-graphite">Clean approvals, conditional sanctions, referrals, a tampered salary slip and a PEP match. All synthetic.</p>
          </div>
          <ButtonLink to="/cases/new" variant="secondary">
            Upload a persona's documents
          </ButtonLink>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(personas.data ?? []).map((p) => (
            <PersonaCard key={p.id} p={p} />
          ))}
          {personas.loading && [0, 1, 2].map((i) => <div key={i} className="h-44 animate-skeleton-pulse rounded-card bg-paper/70" />)}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-16">
        <div className="flex flex-col items-start justify-between gap-6 rounded-card bg-sage p-8 sm:flex-row sm:items-center sm:p-10">
          <div>
            <p className="font-display text-3xl font-medium text-ink">From upload to explained decision in under a minute.</p>
            <p className="mt-2 text-graphite">Every rule ID, every document field, every SHAP reason is one click away.</p>
          </div>
          <ButtonLink to="/pipeline" variant="lime" size="lg">
            Open the pipeline <ArrowRight className="size-4" aria-hidden />
          </ButtonLink>
        </div>
        <Disclaimer className="mt-6 justify-center" />
      </section>
    </div>
  );
}
