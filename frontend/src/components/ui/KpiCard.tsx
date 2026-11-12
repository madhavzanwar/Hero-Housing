import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

export type KpiVariant = "white" | "lime" | "sage" | "danger" | "info";

const SURFACE: Record<KpiVariant, { card: string; muted: string; chip: string }> = {
  white: { card: "elevation-card text-ink", muted: "text-graphite", chip: "bg-fog text-ink" },
  lime: { card: "bg-lime text-on-lime border border-lime-dark/50", muted: "text-on-lime/70", chip: "bg-white/60 text-on-lime" },
  sage: { card: "bg-sage text-ink border border-lime-dark/40", muted: "text-graphite", chip: "bg-paper/70 text-ink" },
  danger: { card: "bg-bad-soft text-ink border border-bad-solid/25 elevation-card", muted: "text-graphite", chip: "bg-paper/70 text-bad" },
  info: { card: "bg-info-soft text-ink border border-info-solid/25 elevation-card", muted: "text-graphite", chip: "bg-paper/70 text-info" },
};

export interface KpiProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon: LucideIcon;
  variant?: KpiVariant;
  series?: number[];
  footer?: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/** Bento KPI card: label, icon chip, big Outfit number, optional olive sparkline (FinPilot KpiCard). */
export function KpiCard({ label, value, sub, icon: Icon, variant = "white", series, footer, className, ...rest }: KpiProps) {
  const s = SURFACE[variant];
  const data = (series ?? []).map((v, i) => ({ i, v }));
  const gradId = `spark-${label.replace(/\W/g, "")}`;
  return (
    <div
      className={cn("relative flex min-w-0 flex-col overflow-hidden rounded-card p-5", variant === "white" && "bg-surface", s.card, className)}
      data-testid={rest["data-testid"]}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={cn("text-sm font-medium", s.muted)}>{label}</span>
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full", s.chip)}>
          <Icon className="size-[18px]" strokeWidth={1.75} aria-hidden />
        </span>
      </div>
      <div className="mt-2 font-display text-[28px] font-semibold leading-tight tnum sm:text-3xl">{value}</div>
      {sub && <div className={cn("mt-1 text-xs leading-relaxed", s.muted)}>{sub}</div>}
      {footer && <div className="mt-3">{footer}</div>}
      {data.length > 1 && (
        <div className="pointer-events-none -mx-5 -mb-5 mt-auto h-12 pt-2" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5f7f0c" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#5f7f0c" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke="#5f7f0c" strokeWidth={2} fill={`url(#${gradId})`} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
