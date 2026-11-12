import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "fphl:theme";
const listeners = new Set<() => void>();

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function initial(): Theme {
  const s = stored();
  if (s) return s;
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

let theme: Theme = initial();

export function applyTheme(t: Theme = theme): void {
  document.documentElement.classList.toggle("dark", t === "dark");
}

export function setTheme(t: Theme): void {
  theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* ignore */
  }
  applyTheme(t);
  listeners.forEach((l) => l());
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const t = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => theme,
    () => theme,
  );
  return [t, setTheme];
}

/** Resolved chart colours (CSS variables) for Recharts, which needs literal values. */
export function chartColors(t: Theme) {
  const dark = t === "dark";
  return {
    olive: dark ? "#93b817" : "#5f7f0c",
    lime: "#c6f135",
    ember: "#ff6b1a",
    indigo: "#3b6bff",
    emerald: "#0fb67a",
    amber: "#e09400",
    cyan: "#12a5b8",
    rose: "#f0455a",
    sage: dark ? "#3a4a22" : "#dfe8c4",
    grid: dark ? "rgba(255,255,255,0.07)" : "rgba(13,13,13,0.07)",
    axis: dark ? "#8792a6" : "#7487a3",
    ink: dark ? "#f3f5ee" : "#0d0d0d",
    surface: dark ? "#17191a" : "#ffffff",
    track: dark ? "#2a2e2c" : "#e7eadf",
  };
}
