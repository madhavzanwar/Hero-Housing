import { motion } from "framer-motion";
import { useId } from "react";
import { cn } from "@/lib/utils";

export interface SegmentItem<T extends string> {
  value: T;
  label: string;
  testId?: string;
}

/** White pills with a lime active pill that slides (FinPilot Forecast & Risk tabs). */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  ariaLabel,
  role = "tablist",
  className,
  size = "md",
}: {
  items: SegmentItem<T>[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel: string;
  role?: "tablist" | "radiogroup";
  className?: string;
  size?: "sm" | "md";
}) {
  const id = useId();
  const itemRole = role === "tablist" ? "tab" : "radio";
  return (
    <div role={role} aria-label={ariaLabel} className={cn("flex gap-2 overflow-x-auto pb-1", className)}>
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            type="button"
            role={itemRole}
            aria-selected={role === "tablist" ? active : undefined}
            aria-checked={role === "radiogroup" ? active : undefined}
            data-testid={it.testId}
            onClick={() => onChange(it.value)}
            className={cn(
              "relative shrink-0 cursor-pointer whitespace-nowrap rounded-full border font-medium transition-colors",
              size === "md" ? "min-h-9 px-4 text-[13px]" : "min-h-8 px-3 text-xs",
              active ? "border-lime-dark text-on-lime" : "border-hairline bg-paper text-graphite hover:text-ink",
            )}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 rounded-full bg-lime"
                transition={{ type: "spring", stiffness: 450, damping: 35 }}
              />
            )}
            <span className="relative z-10">{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}
