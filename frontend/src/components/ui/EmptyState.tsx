import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function EmptyState({ icon: Icon, title, children, action, className }: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-4 py-10 text-center", className)}>
      <span className="flex size-11 items-center justify-center rounded-full bg-fog text-pewter">
        <Icon className="size-5" strokeWidth={1.75} aria-hidden />
      </span>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children && <p className="max-w-md text-[13px] text-pewter">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-card border border-bad-solid/25 bg-bad-soft p-5 text-sm text-ink">
      <p className="font-semibold text-bad">Something went wrong</p>
      <p className="mt-1 text-graphite">{error.message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 rounded-chip border border-mist bg-paper px-3 py-1.5 text-xs font-medium">
          Try again
        </button>
      )}
    </div>
  );
}
