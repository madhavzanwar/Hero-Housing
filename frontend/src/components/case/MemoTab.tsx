import { Printer, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { dateTime } from "@/lib/format";
import type { CaseDetail } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { LogoMark } from "@/components/layout/Logo";

export type DocKind = "memo" | "letter";

export function MemoTab({ c, kind, onKind }: { c: CaseDetail; kind: DocKind; onKind: (k: DocKind) => void }) {
  const doc = useAsync(() => (kind === "memo" ? api.memo(c.id) : api.sanctionLetter(c.id)), `${c.id}:${kind}:${c.overrides.length}`);
  const title = kind === "memo" ? "Credit Memo" : c.decision.outcome === "DECLINE" ? "Letter of Regret" : c.decision.outcome === "REFER" ? "Referral Note" : "Sanction Letter & KFS";
  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Segmented<DocKind>
          ariaLabel="Document"
          value={kind}
          onChange={onKind}
          items={[
            { value: "memo", label: "Credit memo" },
            { value: "letter", label: "Outcome letter" },
          ]}
        />
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-pewter md:inline">Tip: choose "Save as PDF" in the print dialog.</span>
          <Button variant="navy" size="sm" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden /> Print / Save PDF
          </Button>
        </div>
      </div>

      <article className="print-sheet mx-auto w-full max-w-[860px] rounded-[20px] bg-surface px-6 py-8 shadow-[0_10px_40px_-18px_rgba(13,13,13,0.35)] sm:px-12 sm:py-12">
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b-2 border-ink pb-5">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg border border-mist bg-paper">
              <LogoMark size={24} />
            </span>
            <div>
              <p className="font-display text-lg font-semibold text-ink">
                FinPilot HomeLoan<span className="text-ember">.</span>
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-pewter">Explainable underwriting · {title}</p>
            </div>
          </div>
          <div className="text-right font-mono text-[11px] leading-relaxed text-graphite">
            <p className="font-semibold text-ink">DOC REF: FPHL-{c.id}</p>
            <p>Policy {c.decision.policy_version}</p>
            <p>Decided {dateTime(c.decision.decided_at)}</p>
            <p>Classification: Confidential</p>
          </div>
        </header>
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <Chip tone="accent">{kind === "memo" ? "INTERNAL CREDIT MEMO" : "CUSTOMER LETTER (DRAFT)"}</Chip>
          <Chip tone="success">
            <ShieldCheck className="size-3" aria-hidden /> Hash-chained audit
          </Chip>
        </div>
        {doc.error ? (
          <ErrorState error={doc.error} onRetry={doc.reload} />
        ) : doc.data == null ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <Markdown>{doc.data}</Markdown>
        )}
        <footer className="mt-8 border-t border-hairline pt-4 text-[11px] text-pewter">{c.disclaimer} Synthetic data — not a real credit offer.</footer>
      </article>
    </div>
  );
}
