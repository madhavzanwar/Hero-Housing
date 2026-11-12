import { ArrowRight, Gavel, Sparkles, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { dateTime, inr, rate } from "@/lib/format";
import { OUTCOME_LABEL } from "@/lib/labels";
import type { CaseDetail, Condition, DecisionOutcome } from "@/lib/types";
import { DECISION_OUTCOMES } from "@/lib/types";
import { cn, num } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { TextAreaField, TextField } from "@/components/ui/Field";
import { OutcomeChip } from "@/components/ui/Badges";
import { Disclaimer, Label, RuleId } from "@/components/ui/misc";

function AnalysisCard({ c }: { c: CaseDetail }) {
  const d = c.decision;
  const issues = d.rules_fired.filter((r) => r.outcome === "FAIL" || r.outcome === "WARN");
  return (
    <Card className="border-lime-dark/30 bg-sage" data-testid="decision-card">
      <p className="text-sm font-medium text-graphite">Copilot's analysis</p>
      <p className="mt-2 flex items-start gap-2 text-[15px] font-semibold text-ink">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-olive" aria-hidden />
        <span>
          {OUTCOME_LABEL[d.outcome]}
          {d.sanctioned_amount > 0 && ` — ${inr(d.sanctioned_amount)} over ${d.tenure_months} months at ${rate(d.rate)} (EMI ${inr(d.emi)}).`}
        </span>
      </p>

      <Label className="mt-4 block">Why</Label>
      <ul className="mt-1.5 space-y-1.5">
        {d.reasons.map((r, i) => (
          <li key={i} className="flex gap-2 text-sm text-ink">
            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-olive" />
            <span>{r}</span>
          </li>
        ))}
      </ul>

      {d.conditions.length > 0 && (
        <>
          <Label className="mt-4 block">What to do</Label>
          <ol className="mt-1.5 space-y-2">
            {d.conditions.map((cond, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-ink">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-paper text-[11px] font-semibold tnum">{i + 1}</span>
                <span className="min-w-0">
                  {cond.text}{" "}
                  <span className="ml-1 inline-flex align-middle">
                    <Chip tone="outline" className="px-1.5 py-0 font-mono text-[10px]">
                      {cond.code}
                    </Chip>
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </>
      )}

      {issues.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-graphite">Driven by</span>
          {issues.filter((r, i) => issues.findIndex((x) => x.rule_id === r.rule_id) === i).slice(0, 8).map((r) => (
            <RuleId key={r.rule_id} id={r.rule_id} className={r.outcome === "FAIL" ? "border-bad-solid/40" : undefined} />
          ))}
        </div>
      )}
      <p className="mt-4 text-[11px] text-graphite">
        Three lanes: evidence (documents, bank) → assessment (eligibility, PD, Monte Carlo) → decision. Model alone would say{" "}
        <strong className="text-ink">{OUTCOME_LABEL[d.model_suggested]}</strong>; policy rules take precedence.
      </p>
    </Card>
  );
}

function pathOptions(conds: Condition[]): { title: string; text: string; highlight?: string }[] {
  const out: { title: string; text: string; highlight?: string }[] = [];
  for (const c of conds) {
    const p = c.params;
    if (c.code === "REDUCE_AMOUNT") out.push({ title: "Reduce to", highlight: inr(num(p.amount) ?? 0), text: c.text });
    else if (c.code === "ADD_CO_APPLICANT") out.push({ title: "Add co-applicant earning", highlight: `${inr(num(p.additional_income) ?? 0)}/mo`, text: c.text });
    else if (c.code === "INCREASE_TENURE") out.push({ title: "Stretch tenure to", highlight: `${num(p.tenure_months) ?? num(p.months) ?? ""} months`, text: c.text });
    else if (c.code === "CLEAR_EMI") out.push({ title: "Close existing loans", highlight: `${inr(num(p.existing_emi) ?? 0)}/mo`, text: c.text });
  }
  return out;
}

function PathToApproval({ c }: { c: CaseDetail }) {
  const opts = pathOptions(c.decision.conditions);
  const d = c.decision;
  if (d.outcome === "APPROVE") {
    return (
      <div className="flex h-full flex-col justify-between rounded-card border border-lime-dark/50 bg-lime p-6 text-on-lime">
        <div>
          <p className="text-sm font-medium text-on-lime/70">Path to approval</p>
          <p className="mt-2 font-display text-[30px] font-semibold leading-tight">Clean approval. Nothing to fix.</p>
          <p className="mt-2 text-sm text-on-lime/75">All policy checks passed. Review the sanction letter and Key Facts Statement before issue.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col rounded-card border border-lime-dark/50 bg-lime p-6 text-on-lime">
      <p className="text-sm font-medium text-on-lime/70">Path to approval</p>
      {opts.length === 0 ? (
        <>
          <p className="mt-2 font-display text-[28px] font-semibold leading-tight">
            {d.outcome === "DECLINE" ? "No safe restructure within policy." : "Needs a human call."}
          </p>
          <p className="mt-2 text-sm text-on-lime/75">
            {d.outcome === "DECLINE"
              ? "The binding failures are not curable by amount or tenure. Written reasons go out with the letter of regret."
              : "Resolve the referred items (see conditions), then re-run or override with a recorded reason."}
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 font-display text-[28px] font-semibold leading-[1.1]">
            How to get to <span className="whitespace-nowrap rounded-full border-2 border-on-lime/80 px-2">yes</span>?
          </p>
          <ul className="mt-4 space-y-2.5">
            {opts.map((o, i) => (
              <li key={i} className="rounded-2xl bg-white/45 p-3">
                <p className="text-xs font-medium text-on-lime/70">
                  {i > 0 ? "or · " : ""}
                  {o.title}
                </p>
                <p className="font-display text-2xl font-semibold tnum text-[#a83a00]">{o.highlight}</p>
                <p className="mt-0.5 text-xs text-on-lime/80">{o.text}</p>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="min-h-5 flex-1" />
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("fphl:open-copilot"))}
        className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-full bg-white text-sm font-semibold text-[#0d0d0d] hover:bg-white/85"
      >
        Ask the Copilot a what-if <ArrowRight className="size-4" aria-hidden />
      </button>
    </div>
  );
}

function OverridePanel({ c, onUpdated }: { c: CaseDetail; onUpdated: (c: CaseDetail) => void }) {
  const [to, setTo] = useState<DecisionOutcome | null>(null);
  const [who, setWho] = useState("");
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = to !== null && who.trim().length >= 2 && reason.trim().length >= 5;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid || !to) return;
    setBusy(true);
    try {
      const updated = await api.override(c.id, {
        underwriter: who.trim(),
        to_outcome: to,
        reason: reason.trim(),
        sanctioned_amount: amount ? Number(amount) : null,
      });
      onUpdated(updated);
      toast.success(`Override recorded: ${OUTCOME_LABEL[to]}`);
      setReason("");
      setTo(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Override failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Underwriter override"
        subtitle="Human-in-the-loop. Every override needs a reason and is written to the hash-chained audit trail."
        action={<Gavel className="size-5 text-pewter" aria-hidden />}
      />
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div>
          <p id="override-outcome-label" className="mb-1.5 text-[13px] font-medium text-graphite">
            New outcome <span className="text-pewter">(current: {OUTCOME_LABEL[c.decision.outcome]})</span>
          </p>
          <div role="radiogroup" aria-labelledby="override-outcome-label" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {DECISION_OUTCOMES.map((o) => (
              <button
                key={o}
                type="button"
                role="radio"
                aria-checked={to === o}
                data-testid={`override-outcome-${o}`}
                onClick={() => setTo(o)}
                className={cn(
                  "min-h-10 rounded-full border px-3 text-[13px] font-medium transition-colors",
                  to === o ? "border-lime-dark bg-lime text-on-lime" : "border-mist bg-paper text-graphite hover:text-ink",
                )}
              >
                {OUTCOME_LABEL[o]}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField label="Underwriter name" data-testid="override-underwriter" value={who} onChange={(e) => setWho(e.target.value)} placeholder="e.g. A. Underwriter" required autoComplete="name" />
          <TextField
            label="Sanction amount (optional, ₹)"
            type="number"
            min={0}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={c.decision.sanctioned_amount ? String(c.decision.sanctioned_amount) : "—"}
          />
        </div>
        <TextAreaField
          label="Reason (required)"
          data-testid="override-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="What evidence justifies deviating from the engine? Cite documents or rule IDs."
          required
          minLength={5}
          hint={reason.trim().length > 0 && reason.trim().length < 5 ? "At least 5 characters" : "Recorded verbatim in the audit trail"}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-pewter">Engine said {OUTCOME_LABEL[c.decision.engine_outcome]}. Overrides never delete the engine's decision.</p>
          <Button type="submit" variant="navy" data-testid="override-submit" disabled={!valid || busy}>
            {busy ? "Saving…" : "Apply override"}
          </Button>
        </div>
      </form>

      {c.overrides.length > 0 && (
        <div className="mt-5 border-t border-hairline pt-4">
          <Label>Override history</Label>
          <ul className="mt-2 space-y-2">
            {c.overrides.map((o, i) => (
              <li key={i} className="rounded-surface bg-fog p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <OutcomeChip outcome={o.from_outcome} short />
                  <ArrowRight className="size-3.5 text-pewter" aria-hidden />
                  <OutcomeChip outcome={o.to_outcome} short />
                  <span className="ml-auto flex items-center gap-1 text-xs text-pewter">
                    <UserPlus className="size-3" aria-hidden /> {o.underwriter} · {dateTime(o.at)}
                  </span>
                </div>
                <p className="mt-1.5 text-graphite">{o.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function DecisionTab({ c, onUpdated }: { c: CaseDetail; onUpdated: (c: CaseDetail) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <AnalysisCard c={c} />
        </div>
        <div className="lg:col-span-4">
          <PathToApproval c={c} />
        </div>
      </div>
      <OverridePanel c={c} onUpdated={onUpdated} />
      <Disclaimer text={c.disclaimer} />
    </div>
  );
}
