import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type Tone = "neutral" | "accent" | "outline" | "success" | "warning" | "danger" | "info" | "lime" | "cyan" | "solid-danger";

const TONES: Record<Tone, string> = {
  neutral: "bg-fog text-graphite border-hairline",
  accent: "bg-ember/10 text-ember-dark border-ember/25 font-semibold",
  outline: "bg-paper text-graphite border-mist",
  success: "bg-ok-soft text-ok border-ok-solid/25",
  warning: "bg-warn-soft text-warn border-warn-solid/25",
  danger: "bg-bad-soft text-bad border-bad-solid/25",
  info: "bg-info-soft text-info border-info-solid/25",
  cyan: "bg-cyan-soft text-cyan border-cyan/25",
  lime: "bg-lime text-on-lime border-lime-dark",
  "solid-danger": "bg-bad-solid text-white border-bad-solid",
};

interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
}

/** 10 px-radius chip for categories, tags and statuses. Always carries a word. */
export function Chip({ className, tone = "neutral", dot = false, children, ...props }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip border px-2 py-0.5 text-xs font-medium tracking-tight",
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
