import { ArrowUp, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import type { CopilotAnswer } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Chip } from "@/components/ui/Chip";
import { Markdown } from "@/components/ui/Markdown";
import { SUGGESTIONS } from "@/lib/copilot";


interface Turn {
  q: string;
  a?: CopilotAnswer;
  error?: string;
}

function CitationChips({ a }: { a: CopilotAnswer }) {
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      {a.citations.filter((c, i, all) => all.findIndex((x) => x.kind === c.kind && x.ref === c.ref) === i).map((c, i) => (
        <span
          key={`${c.ref}-${i}`}
          title={c.text}
          className={cn(
            "inline-flex max-w-[16rem] items-center gap-1 truncate rounded-md border px-1.5 py-0.5 font-mono text-[11px]",
            c.kind === "rule" ? "border-lime-dark/50 bg-paper text-ink" : "border-hairline bg-paper/70 text-graphite",
          )}
        >
          {c.kind === "document" ? "doc: " : c.kind === "metric" ? "metric: " : c.kind === "policy" ? "policy: " : ""}
          {c.ref}
        </span>
      ))}
      <Chip tone="outline" className="ml-auto text-[10px]">
        {a.engine}
      </Chip>
    </div>
  );
}

/** Case-scoped grounded Q&A. Answers carry rule-ID citation chips. */
export function CopilotChat({ caseId, compact = false, greeting }: { caseId: string; compact?: boolean; greeting?: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns([]);
  }, [caseId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { q }]);
    try {
      const a = await api.copilot(caseId, q);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Copilot is unavailable";
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  const lastAnswered = turns.reduce((acc, t, i) => (t.a ? i : acc), -1);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-1 pb-4">
        {turns.length === 0 && (
          <div className={cn("flex flex-col items-center text-center", compact ? "pt-4" : "pt-10")}>
            <h2 className={cn("font-display font-medium text-ink", compact ? "text-2xl" : "text-3xl sm:text-4xl")}>
              {greeting ?? "Hey, underwriter. What should we check?"}
            </h2>
            <p className="mt-2 max-w-md text-sm text-graphite">
              Answers come only from this case file and the credit policy, with rule IDs you can verify.
            </p>
            <div className="mt-6 flex max-w-2xl flex-wrap justify-center gap-2">
              {SUGGESTIONS.slice(0, compact ? 4 : 6).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void ask(s)}
                  className="min-h-9 rounded-full border border-mist bg-paper px-3.5 text-[13px] text-graphite transition-colors hover:border-lime-dark hover:text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-sm text-paper">{t.q}</p>
            </div>
            <div className="flex items-start gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-lime text-on-lime">
                <Sparkles className="size-4" aria-hidden />
              </span>
              <div
                className="min-w-0 max-w-[92%] rounded-2xl rounded-tl-md bg-tint-lime px-4 py-3 text-sm text-ink"
                data-testid={i === lastAnswered ? "copilot-answer" : undefined}
                aria-live="polite"
              >
                {t.a ? (
                  <>
                    <div className="[&_.statement-md_p]:text-ink [&_.statement-md_li]:text-ink">
                      <Markdown>{t.a.answer}</Markdown>
                    </div>
                    <CitationChips a={t.a} />
                  </>
                ) : t.error ? (
                  <p className="text-bad">{t.error}</p>
                ) : (
                  <span className="inline-flex gap-1" aria-label="Thinking">
                    {[0, 1, 2].map((d) => (
                      <span key={d} className="size-1.5 animate-bounce rounded-full bg-olive" style={{ animationDelay: `${d * 120}ms` }} />
                    ))}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={onSubmit} className="rounded-[20px] border border-mist bg-paper p-2 shadow-sm">
        <label htmlFor={`copilot-input-${caseId}`} className="sr-only">
          Ask the Copilot about this case
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id={`copilot-input-${caseId}`}
            data-testid="copilot-input"
            rows={compact ? 1 : 2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask(input);
              }
            }}
            placeholder={compact ? "Ask about this case…" : "Ask about FOIR, LTV, documents, rules or a what-if…"}
            className="min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] text-ink outline-none placeholder:text-pewter"
          />
          <button
            type="submit"
            data-testid="copilot-send"
            disabled={busy || !input.trim()}
            aria-label="Send question"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-lime text-on-lime transition hover:bg-lime-dark disabled:opacity-40"
          >
            <ArrowUp className="size-4" />
          </button>
        </div>
        <p className="px-2 pb-1 text-[11px] text-pewter">Grounded in the case file; cites rule IDs. Decision support only.</p>
      </form>
    </div>
  );
}
