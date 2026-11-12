import {
  BookOpenCheck,
  FilePlus2,
  FlaskConical,
  LayoutDashboard,
  PieChart,
  Scale,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

export interface NavLink {
  to: string;
  label: string;
  icon: LucideIcon;
  testId?: string;
}

export interface NavGroup {
  label: string;
  tone: string;
  links: NavLink[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Underwriting",
    tone: "text-ember-dark",
    links: [
      { to: "/pipeline", label: "Pipeline", icon: LayoutDashboard, testId: "nav-pipeline" },
      { to: "/cases/new", label: "New case", icon: FilePlus2, testId: "nav-new-case" },
      { to: "/copilot", label: "Underwriting Copilot", icon: Sparkles, testId: "nav-copilot" },
    ],
  },
  {
    label: "Insight",
    tone: "text-ok",
    links: [{ to: "/portfolio", label: "Portfolio", icon: PieChart, testId: "nav-portfolio" }],
  },
  {
    label: "Governance",
    tone: "text-info",
    links: [
      { to: "/policy", label: "Credit policy", icon: Scale, testId: "nav-policy" },
      { to: "/model", label: "Model card", icon: FlaskConical, testId: "nav-model" },
    ],
  },
];

export const PAGE_TITLES: { prefix: string; title: string }[] = [
  { prefix: "/cases/new", title: "New case" },
  { prefix: "/cases/", title: "Case file" },
  { prefix: "/pipeline", title: "Pipeline" },
  { prefix: "/copilot", title: "Underwriting Copilot" },
  { prefix: "/portfolio", title: "Portfolio" },
  { prefix: "/policy", title: "Credit policy" },
  { prefix: "/model", title: "Model card" },
];

export const DocsIcon = BookOpenCheck;
