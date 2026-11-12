import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-skeleton-pulse rounded-surface bg-paper/70", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading">
      <Skeleton className="h-10 w-72" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 rounded-card" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-card" />
    </div>
  );
}
