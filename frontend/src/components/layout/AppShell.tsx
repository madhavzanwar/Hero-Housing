import { AnimatePresence, motion } from "framer-motion";
import { Bell, Database, Menu, MessageCircle, Moon, PanelLeft, Search, Sun, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useMode, getModeReason } from "@/lib/mode";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { CopilotChat } from "@/components/copilot/CopilotChat";
import { MobileSidebar, Sidebar } from "./Sidebar";
import { PAGE_TITLES } from "./nav";

const ROLES = ["RM", "Underwriter", "Credit head"] as const;
type Role = (typeof ROLES)[number];

function RoleSwitcher() {
  const [role, setRole] = useState<Role>(() => {
    try {
      const r = localStorage.getItem("fphl:role");
      return (ROLES as readonly string[]).includes(r ?? "") ? (r as Role) : "Underwriter";
    } catch {
      return "Underwriter";
    }
  });
  return (
    <div role="radiogroup" aria-label="Role" className="flex items-center gap-0.5 rounded-full border border-mist bg-paper/80 p-1 backdrop-blur-md">
      {ROLES.map((r) => {
        const active = r === role;
        return (
          <button
            key={r}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              setRole(r);
              try {
                localStorage.setItem("fphl:role", r);
              } catch {
                /* ignore */
              }
            }}
            className={cn(
              "relative flex min-h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs font-medium",
              active ? "text-ink" : "text-graphite hover:text-ink",
            )}
          >
            {active && (
              <motion.span
                layoutId="role-pill"
                className="absolute inset-0 rounded-full border border-mist bg-paper shadow-[0_1px_4px_rgba(0,0,0,0.08)]"
                transition={{ type: "spring", stiffness: 450, damping: 35 }}
              />
            )}
            <span className={cn("relative z-10 size-1.5 rounded-full", active ? "bg-ember" : "bg-steel/60")} aria-hidden />
            <span className="relative z-10">{r}</span>
          </button>
        );
      })}
    </div>
  );
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      data-testid="theme-toggle"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
      className={cn("flex size-9 items-center justify-center rounded-full border border-mist bg-paper text-ink hover:bg-fog", className)}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

function DemoChip() {
  const mode = useMode();
  if (mode !== "demo") return null;
  return (
    <span
      title={`Offline snapshot (${getModeReason()}). Overrides are saved in this browser.`}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-warn-solid/30 bg-warn-soft px-2.5 py-1 text-xs font-semibold text-warn"
      data-testid="demo-chip"
    >
      <Database className="size-3.5" aria-hidden />
      <span className="hidden sm:inline">Demo mode — preloaded personas</span>
      <span className="sm:hidden">Demo</span>
    </span>
  );
}

function CopilotSheet({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  const navigate = useNavigate();
  return (
    <motion.div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Copilot" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <button type="button" aria-label="Close Copilot" className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={onClose} />
      <motion.div
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ type: "spring", stiffness: 380, damping: 36 }}
        className="absolute inset-y-3 right-3 flex w-[min(460px,calc(100vw-1.5rem))] flex-col rounded-card border border-hairline bg-surface p-4 shadow-2xl"
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <div>
            <p className="font-display text-lg font-medium text-ink">Underwriting Copilot</p>
            <p className="text-xs text-pewter">{caseId ? <span className="font-mono">{caseId}</span> : "Open a case to ask about it"}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close Copilot" className="rounded-full p-2 text-graphite hover:bg-fog">
            <X className="size-4" />
          </button>
        </div>
        {caseId ? (
          <CopilotChat caseId={caseId} compact greeting="What should we check on this case?" />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-graphite">
            <p>The floating Copilot is scoped to the case you are viewing.</p>
            <button
              type="button"
              className="rounded-full bg-lime px-4 py-2 text-sm font-semibold text-on-lime"
              onClick={() => {
                onClose();
                navigate("/copilot");
              }}
            >
              Open Copilot workspace
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const caseMatch = useMatch("/cases/:id");
  const caseId = caseMatch && caseMatch.params.id !== "new" ? (caseMatch.params.id ?? null) : null;
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const title = PAGE_TITLES.find((p) => pathname.startsWith(p.prefix))?.title ?? "FinPilot HomeLoan";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setCopilotOpen(false);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const open = () => setCopilotOpen(true);
    window.addEventListener("fphl:open-copilot", open);
    return () => window.removeEventListener("fphl:open-copilot", open);
  }, []);

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-chip focus:bg-lime focus:px-3 focus:py-2 focus:text-on-lime">
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} />
      <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex h-16 shrink-0 items-center gap-2 bg-background/70 px-4 backdrop-blur-md sm:px-6">
          <button
            type="button"
            className="hidden rounded-lg p-2 text-graphite hover:bg-fog hover:text-ink lg:flex"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <PanelLeft className="size-4" />
          </button>
          <button type="button" className="rounded-lg p-2 text-graphite hover:bg-fog lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
          <span className="hidden h-4 w-px bg-mist lg:block" aria-hidden />
          <p className="truncate font-display text-xl font-semibold text-ink sm:text-2xl">{title}</p>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            <DemoChip />
            <Link
              to="/pipeline"
              className="hidden h-9 w-44 items-center gap-2 rounded-xl border border-hairline bg-paper px-3 text-sm text-pewter shadow-sm md:flex xl:w-52"
              aria-label="Search cases in the pipeline"
            >
              <Search className="size-4" aria-hidden />
              <span>Search cases…</span>
              <kbd className="ml-auto rounded border border-mist bg-fog px-1.5 text-[10px] font-semibold text-graphite">⌘ K</kbd>
            </Link>
            <ThemeToggle />
            <div className="hidden xl:block">
              <RoleSwitcher />
            </div>
            <Link to="/pipeline?filter=REFER" aria-label="Cases awaiting review" className="relative hidden size-9 items-center justify-center rounded-full text-graphite hover:bg-fog sm:flex">
              <Bell className="size-[18px]" />
              <span className="absolute right-1 top-1 size-2 rounded-full bg-ember ring-2 ring-background" aria-hidden />
            </Link>
          </div>
        </header>

        <main id="main" className="mx-auto w-full min-w-0 max-w-[1600px] flex-1 px-4 pb-24 pt-3 sm:px-6 lg:px-8">
          <motion.div key={pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}>
            {children}
          </motion.div>
        </main>
      </div>

      {pathname !== "/copilot" && (
        <button
          type="button"
          onClick={() => setCopilotOpen(true)}
          aria-label="Open Copilot"
          data-testid="copilot-fab"
          className="no-print fixed bottom-5 right-5 z-40 flex size-14 items-center justify-center rounded-full bg-lime text-on-lime shadow-[0_8px_24px_-6px_rgba(95,127,12,0.55)] transition hover:scale-105 hover:bg-lime-dark"
        >
          <MessageCircle className="size-6" strokeWidth={1.9} />
        </button>
      )}
      <AnimatePresence>{copilotOpen && <CopilotSheet caseId={caseId} onClose={() => setCopilotOpen(false)} />}</AnimatePresence>
    </div>
  );
}
