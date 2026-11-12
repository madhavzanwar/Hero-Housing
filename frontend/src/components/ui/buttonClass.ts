import { cn } from "@/lib/utils";

export type ButtonVariant = "lime" | "navy" | "secondary" | "ghost" | "white";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", className?: string): string {
  return cn(
    "inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-chip font-medium transition-all duration-150 active:scale-[0.98]",
    "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40",
    size === "sm" && "min-h-9 px-3 py-1.5 text-xs",
    size === "md" && "min-h-10 px-4 py-2 text-sm",
    size === "lg" && "min-h-12 px-6 py-3 text-base font-semibold",
    size === "icon" && "size-9 p-0",
    variant === "lime" &&
      "border border-lime-dark/40 bg-lime font-semibold text-on-lime shadow-[0_2px_12px_rgba(166,209,26,0.35)] hover:bg-lime-dark",
    variant === "navy" && "border border-navy/30 bg-navy text-white shadow-[0_2px_10px_rgba(23,37,84,0.22)] hover:bg-navy-light",
    variant === "secondary" && "border border-mist bg-paper text-ink hover:bg-fog",
    variant === "white" && "border border-hairline bg-paper text-ink shadow-sm hover:bg-fog",
    variant === "ghost" && "text-graphite hover:bg-fog hover:text-ink",
    className,
  );
}

