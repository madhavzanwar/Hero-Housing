import { useSyncExternalStore } from "react";

/**
 * Connection mode. "live" talks to the FastAPI backend; "demo" serves the
 * static snapshot in src/demo/snapshot.json (backend unreachable or VITE_DEMO=1).
 */
export type Mode = "unknown" | "live" | "demo";

let mode: Mode = import.meta.env.VITE_DEMO === "1" ? "demo" : "unknown";
let reason = mode === "demo" ? "VITE_DEMO=1" : "";
const listeners = new Set<() => void>();

export function getMode(): Mode {
  return mode;
}

export function getModeReason(): string {
  return reason;
}

export function setMode(next: Mode, why = ""): void {
  if (mode === next) return;
  mode = next;
  reason = why;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useMode(): Mode {
  return useSyncExternalStore(subscribe, getMode, getMode);
}
