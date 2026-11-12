import type { ComponentProps, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CardProps extends ComponentProps<"div"> {
  hoverable?: boolean;
}

/** White 28 px bento card (FinPilot ui/Card). */
export function Card({ className, hoverable = false, ...props }: CardProps) {
  return (
    <div
      className={cn("relative min-w-0 rounded-card p-4 elevation-card sm:p-5", hoverable && "elevation-card-hover", className)}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  className,
  display = true,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
  display?: boolean;
}) {
  return (
    <div className={cn("mb-4 flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h3 className={cn("text-ink", display ? "font-display text-lg font-medium" : "text-base font-semibold")}>{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-pewter">{subtitle}</p>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
    </div>
  );
}

/** Inner well / sub-tile (16 px radius). */
export function Well({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-surface bg-fog p-3.5", className)} {...props} />;
}
