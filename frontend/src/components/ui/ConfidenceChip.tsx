import { cn } from "@/lib/utils";

/** Solid emerald ≥ 75 %, fog ≥ 45 %, dashed below (FinPilot ui/ConfidenceChip). */
export function ConfidenceChip({ value, className, label = "conf." }: { value: number; className?: string; label?: string }) {
  const n = value <= 1 ? value : value / 100;
  const p = Math.round(n * 100);
  const tier = n >= 0.75 ? "high" : n >= 0.45 ? "medium" : "low";
  return (
    <span
      title={`Confidence ${p}%`}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip px-2 py-0.5 text-[11px] font-semibold",
        tier === "high" && "border border-ok-solid/30 bg-ok-soft text-ok",
        tier === "medium" && "border border-hairline bg-fog text-graphite",
        tier === "low" && "border border-dashed border-steel bg-paper text-pewter",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn("size-1.5 rounded-full", tier === "high" ? "bg-ok-solid" : tier === "medium" ? "bg-warn-solid" : "bg-steel")}
      />
      <span className="tnum">
        {p}% {label}
      </span>
    </span>
  );
}
