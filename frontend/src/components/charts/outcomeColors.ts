import type { DecisionOutcome } from "@/lib/types";
import type { Theme } from "@/lib/theme";

export function outcomeColor(o: DecisionOutcome, theme: Theme): string {
  switch (o) {
    case "APPROVE":
      return theme === "dark" ? "#93b817" : "#5f7f0c";
    case "APPROVE_WITH_CONDITIONS":
      return "#e09400";
    case "REFER":
      return "#3b6bff";
    case "DECLINE":
      return "#f0455a";
  }
}
