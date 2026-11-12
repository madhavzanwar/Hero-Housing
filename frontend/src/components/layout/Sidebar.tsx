import { motion } from "framer-motion";
import { Plus, X } from "lucide-react";
import { NavLink as RouterLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { ButtonLink } from "@/components/ui/Button";
import { NAV_GROUPS } from "./nav";
import { Wordmark } from "./Logo";

function isActive(pathname: string, to: string): boolean {
  if (to === "/cases/new") return pathname === "/cases/new";
  if (to === "/pipeline") return pathname.startsWith("/pipeline") || (pathname.startsWith("/cases/") && pathname !== "/cases/new");
  return pathname.startsWith(to);
}

function SidebarBody({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <div className="flex h-full flex-col">
      <div className={cn("flex items-center px-3 pb-2 pt-3", collapsed && "justify-center px-0")}>
        <RouterLink to="/" aria-label="FinPilot HomeLoan home" onClick={onNavigate} className="flex min-w-0 flex-1 items-center rounded-xl p-1">
          <Wordmark compact={collapsed} />
        </RouterLink>
        {!collapsed && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-lime shadow-[0_0_8px_rgba(198,241,53,0.8)]" />}
      </div>

      <nav aria-label="Main" className="mt-2 flex-1 space-y-5 overflow-y-auto px-2">
        {NAV_GROUPS.map((g) => (
          <div key={g.label}>
            {!collapsed && <p className="px-3 pb-1.5 text-xs font-medium text-pewter">{g.label}</p>}
            <ul className="space-y-0.5">
              {g.links.map(({ to, label, icon: Icon, testId }) => {
                const active = isActive(pathname, to);
                return (
                  <li key={to}>
                    <RouterLink
                      to={to}
                      data-testid={testId}
                      onClick={onNavigate}
                      title={collapsed ? label : undefined}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "relative flex min-h-9 items-center gap-2.5 rounded-full px-3 text-sm font-medium transition-colors",
                        collapsed && "justify-center px-0",
                        active ? "text-on-lime" : "text-graphite hover:bg-ink/5 hover:text-ink",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="sidebar-active"
                          className="absolute inset-0 rounded-full bg-lime"
                          transition={{ type: "spring", stiffness: 450, damping: 35 }}
                        />
                      )}
                      <Icon className={cn("relative z-10 size-4 shrink-0", active ? "text-on-lime" : g.tone)} strokeWidth={1.75} aria-hidden />
                      {!collapsed && <span className="relative z-10 truncate">{label}</span>}
                    </RouterLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="p-3">
          <ButtonLink to="/cases/new" variant="lime" className="w-full rounded-full" onClick={onNavigate}>
            <Plus className="size-4" aria-hidden /> New case
          </ButtonLink>
          <p className="mt-3 px-1 text-[11px] leading-snug text-pewter">Hero Housing Fintech Challenge · PS2. Synthetic personas only.</p>
        </div>
      )}
    </div>
  );
}

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <aside
      className={cn(
        "sticky top-3 m-3 hidden h-[calc(100vh-1.5rem)] shrink-0 rounded-card border border-hairline bg-sidebar shadow-sm transition-[width] duration-300 lg:block",
        collapsed ? "w-[68px]" : "w-[232px]",
      )}
    >
      <SidebarBody collapsed={collapsed} />
    </aside>
  );
}

export function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
      <button type="button" aria-label="Close navigation" className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ x: -280 }}
        animate={{ x: 0 }}
        transition={{ type: "spring", stiffness: 400, damping: 40 }}
        className="absolute inset-y-3 left-3 w-[260px] rounded-card border border-hairline bg-sidebar shadow-xl"
      >
        <button type="button" onClick={onClose} aria-label="Close navigation" className="absolute right-3 top-4 z-10 rounded-full p-1.5 text-graphite hover:bg-fog">
          <X className="size-4" />
        </button>
        <SidebarBody collapsed={false} onNavigate={onClose} />
      </motion.div>
    </div>
  );
}
