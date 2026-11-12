import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const DISCLAIMER =
  "Decision support for underwriters. Final credit decisions follow the lender's board-approved credit policy and applicable RBI/NHB regulations.";

export function Disclaimer({ text = DISCLAIMER, className }: { text?: string; className?: string }) {
  return (
    <p className={cn("flex items-start gap-2 text-xs text-pewter", className)}>
      <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
      <span>{text} Synthetic data only.</span>
    </p>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[11px] tracking-tight", className)}>{children}</span>;
}

export function RuleId({ id, className }: { id: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-md border border-hairline bg-fog px-1.5 py-0.5 font-mono text-[11px] font-medium text-ink", className)}>
      {id}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="font-display text-[28px] font-medium leading-tight text-ink sm:text-[32px]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-graphite">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("text-[11px] font-semibold uppercase tracking-wider text-pewter", className)}>{children}</span>;
}

export function Bar({ value, tone = "auto", className }: { value: number; tone?: "auto" | "olive" | "bad" | "info"; className?: string }) {
  const v = Math.max(0, Math.min(100, value));
  const color =
    tone === "olive" ? "bg-olive" : tone === "bad" ? "bg-bad-solid" : tone === "info" ? "bg-info-solid" : v >= 70 ? "bg-ok-solid" : v >= 50 ? "bg-warn-solid" : "bg-ember";
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-fog", className)}>
      <div className={cn("h-full rounded-full transition-[width] duration-700", color)} style={{ width: `${v}%` }} />
    </div>
  );
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  const hues = ["bg-lime text-on-lime", "bg-sage text-ink", "bg-info-soft text-info", "bg-warn-soft text-warn", "bg-cyan-soft text-cyan", "bg-ember/15 text-ember-dark"];
  const h = hues[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % hues.length];
  return (
    <span aria-hidden className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold", h, className)}>
      {letters}
    </span>
  );
}
