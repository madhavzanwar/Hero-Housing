import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { ensureMode } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const Landing = lazy(() => import("@/pages/Landing"));
const Pipeline = lazy(() => import("@/pages/Pipeline"));
const NewCase = lazy(() => import("@/pages/NewCase"));
const CaseDetail = lazy(() => import("@/pages/CaseDetail"));
const Copilot = lazy(() => import("@/pages/Copilot"));
const Portfolio = lazy(() => import("@/pages/Portfolio"));
const Policy = lazy(() => import("@/pages/Policy"));
const ModelCard = lazy(() => import("@/pages/ModelCard"));

function Shell({ children }: { children: ReactNode }) {
  return (
    <AppShell>
      <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
    </AppShell>
  );
}

export default function App() {
  const [theme] = useTheme();
  useEffect(() => {
    void ensureMode();
  }, []);
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
      <Routes>
        <Route
          path="/"
          element={
            <Suspense fallback={null}>
              <Landing />
            </Suspense>
          }
        />
        <Route path="/pipeline" element={<Shell><Pipeline /></Shell>} />
        <Route path="/cases/new" element={<Shell><NewCase /></Shell>} />
        <Route path="/cases/:id" element={<Shell><CaseDetail /></Shell>} />
        <Route path="/copilot" element={<Shell><Copilot /></Shell>} />
        <Route path="/portfolio" element={<Shell><Portfolio /></Shell>} />
        <Route path="/policy" element={<Shell><Policy /></Shell>} />
        <Route path="/model" element={<Shell><ModelCard /></Shell>} />
        <Route path="*" element={<Navigate to="/pipeline" replace />} />
      </Routes>
      <Toaster position="bottom-left" theme={theme} richColors closeButton />
    </BrowserRouter>
  );
}
