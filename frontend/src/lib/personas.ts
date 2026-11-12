import type { PersonaInfo } from "./types";

export type PersonaTone = "danger" | "warning" | "info" | "success" | "cyan";

const TAGS: Record<string, { text: string; tone: PersonaTone }> = {
  p07: { text: "Fraud case", tone: "danger" },
  p10: { text: "Prohibited end-use", tone: "danger" },
  p11: { text: "PEP / EDD", tone: "info" },
  p08: { text: "Decline", tone: "danger" },
  p06: { text: "Borderline", tone: "warning" },
  p05: { text: "FOIR breach", tone: "warning" },
  p12: { text: "LTV slab", tone: "warning" },
  p04: { text: "LAP · cash-heavy", tone: "cyan" },
};

export function personaTag(p: Pick<PersonaInfo, "id" | "product">): { text: string; tone: PersonaTone } {
  return TAGS[p.id] ?? (p.product === "LAP" ? { text: "LAP", tone: "cyan" } : { text: "Clean", tone: "success" });
}
