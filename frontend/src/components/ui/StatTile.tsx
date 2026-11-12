import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Tone } from "./Chip";
import { Chip } from "./Chip";

export interface StatTileProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  status?: { tone: Tone; text: string };
  className?: string;
}

/** Dense KPI tile: uppercase label, Outfit value, one-line sub (FinPilot ui/StatTile). */
export function StatTile({ label, value, sub, status, className }: StatTileProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5 rounded-[20px] p-3.5 elevation-card", className)}>
      <div className="flex items-start justify-between gap-1">
        <span className="text-[11px] font-semibold uppercase leading-tight tracking-wider text-pewter">{label}</span>
        {status && (
          <Chip tone={status.tone} className="px-1.5 py-0 text-[10px]">
            {status.text}
          </Chip>
        )}
      </div>
      <div className="truncate font-display text-2xl font-semibold leading-tight text-ink tnum">{value}</div>
      {sub && <div className="truncate text-xs text-graphite">{sub}</div>}
    </div>
  );
}

export function StatStrip({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8", className)}>{children}</div>;
}
