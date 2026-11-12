import type { ReactNode } from "react";

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Themed tooltip body for Recharts `content` render props. */
export function TooltipBox({ title, rows }: { title?: ReactNode; rows: TooltipRow[] }) {
  return (
    <div className="min-w-36 rounded-xl border border-hairline bg-surface px-3 py-2 text-xs shadow-lg">
      {title && <p className="mb-1 font-semibold text-ink">{title}</p>}
      {rows.map((r) => (
        <p key={r.label} className="flex items-center justify-between gap-4 text-graphite">
          <span className="flex items-center gap-1.5">
            {r.color && <span className="size-2 rounded-full" style={{ background: r.color }} aria-hidden />}
            {r.label}
          </span>
          <span className="font-semibold text-ink tnum">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; value?: string; dashed?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-graphite">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          {i.dashed ? (
            <span className="h-0 w-4 border-t-2 border-dashed" style={{ borderColor: i.color }} aria-hidden />
          ) : (
            <span className="size-2.5 rounded-full" style={{ background: i.color }} aria-hidden />
          )}
          <span>{i.label}</span>
          {i.value && <span className="font-semibold text-ink tnum">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}
