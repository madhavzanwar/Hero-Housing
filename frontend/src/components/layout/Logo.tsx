import { cn } from "@/lib/utils";

/** FinPilot mark (three rising pillars + ember needle) with the HomeLoan wordmark. */
export function LogoMark({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden>
      <rect x="5" y="18" width="4.5" height="9" rx="1.2" className="fill-ink" />
      <rect x="12" y="13" width="4.5" height="14" rx="1.2" className="fill-ink" />
      <rect x="19" y="8" width="4.5" height="19" rx="1.2" className="fill-ink" />
      <path d="M6 15 L25 4" stroke="#ff6b1a" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="25.5" cy="4" r="2.2" fill="#ff6b1a" />
    </svg>
  );
}

export function Wordmark({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-mist bg-paper">
        <LogoMark size={20} />
      </span>
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="font-display text-lg font-medium tracking-tight text-ink">
            FinPilot<span className="text-ember">.</span>
          </span>
          <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-pewter">HomeLoan</span>
        </span>
      )}
    </span>
  );
}
