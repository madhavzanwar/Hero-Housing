import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/** 270° arc gauge (FinPilot HealthScoreCard). `value` in [0, max]. */
export function Gauge({
  value,
  max = 100,
  label,
  caption,
  display,
  size = 160,
  className,
}: {
  value: number;
  max?: number;
  label: string;
  caption?: string;
  /** Number shown in the centre when it differs from the arc value (e.g. a 300–900 score). */
  display?: number;
  size?: number;
  className?: string;
}) {
  const r = 58;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  const offset = c - frac * c * 0.75;
  const stroke = frac >= 0.7 ? "stroke-olive" : frac >= 0.5 ? "stroke-warn-solid" : "stroke-ember";
  return (
    <div className={cn("relative flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg className="size-full rotate-[135deg]" viewBox="0 0 140 140" role="img" aria-label={`${label}: ${Math.round(value)} of ${max}`}>
        <circle
          cx="70"
          cy="70"
          r={r}
          className="stroke-paper/80"
          strokeWidth="10"
          fill="transparent"
          strokeDasharray={`${c * 0.75} ${c}`}
          strokeLinecap="round"
        />
        <motion.circle
          cx="70"
          cy="70"
          r={r}
          className={stroke}
          strokeWidth="10"
          fill="transparent"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.1, ease: "easeOut" }}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className={cn("font-display font-semibold leading-none text-ink tnum", size >= 140 ? "text-5xl" : "text-3xl")}>
          {Math.round(display ?? value)}
        </span>
        {caption && <span className="mt-1 text-xs font-medium text-graphite">{caption}</span>}
      </div>
    </div>
  );
}
