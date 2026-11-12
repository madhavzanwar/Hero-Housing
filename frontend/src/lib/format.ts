/** Indian-locale number formatting: ₹45,00,000 · ₹45L · ₹1.1Cr · 62.5% · 12 Nov 2026. */

const inr0 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Full rupee amount with Indian grouping: 4500000 → "₹45,00,000". */
export function inr(v: number | null | undefined, opts: { paise?: boolean } = {}): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  return `${sign}₹${opts.paise ? inr2.format(abs) : inr0.format(Math.round(abs))}`;
}

/** Short form for dense tables: ₹45L, ₹1.1Cr, ₹85K. */
export function inrShort(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  const trim = (n: number, d: number) => n.toFixed(d).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
  if (a >= 1e7) return `${sign}₹${trim(a / 1e7, a >= 1e8 ? 1 : 2)}Cr`;
  if (a >= 1e5) return `${sign}₹${trim(a / 1e5, a >= 1e6 ? 1 : 2)}L`;
  if (a >= 1e3) return `${sign}₹${trim(a / 1e3, 1)}K`;
  return `${sign}₹${Math.round(a)}`;
}

/** Fraction → percent string: 0.625 → "62.5%". */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits).replace(/\.0+$/, "")}%`;
}

export function rate(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

export function number(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(v);
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function date(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : dateFmt.format(d);
}

export function dateTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : dateTimeFmt.format(d);
}

/** "2026-08" → "Aug 26". */
export function monthLabel(m: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(m);
  if (!match) return m;
  const d = new Date(Number(match[1]), Number(match[2]) - 1, 1);
  return d.toLocaleString("en-IN", { month: "short" }) + " " + match[1].slice(2);
}

export function ms(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v < 1000) return `${Math.round(v)} ms`;
  return `${(v / 1000).toFixed(1)} s`;
}

export function months(n: number | null | undefined): string {
  if (n == null) return "—";
  const y = Math.floor(n / 12);
  const m = n % 12;
  return m === 0 ? `${n} mo (${y} yr)` : `${n} mo`;
}
