import { ArrowLeft } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { CaseDetail as Case } from "@/lib/types";
import { ErrorState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { Segmented } from "@/components/ui/Segmented";
import { CaseHeader } from "@/components/case/CaseHeader";
import { DecisionHero } from "@/components/case/DecisionHero";
import { DecisionTab } from "@/components/case/DecisionTab";
import { DocumentsTab } from "@/components/case/DocumentsTab";
import { BankTab } from "@/components/case/BankTab";
import { EligibilityTab } from "@/components/case/EligibilityTab";
import { RiskTab } from "@/components/case/RiskTab";
import { CapacityTab } from "@/components/case/CapacityTab";
import { FraudTab } from "@/components/case/FraudTab";
import { RulesTab } from "@/components/case/RulesTab";
import { MemoTab, type DocKind } from "@/components/case/MemoTab";
import { AuditTab } from "@/components/case/AuditTab";

const TABS = [
  { value: "decision", label: "Decision" },
  { value: "documents", label: "Documents" },
  { value: "bank", label: "Bank analytics" },
  { value: "eligibility", label: "Eligibility" },
  { value: "risk", label: "Risk & SHAP" },
  { value: "capacity", label: "Capacity" },
  { value: "fraud", label: "Fraud & compliance" },
  { value: "rules", label: "Rules fired" },
  { value: "memo", label: "Memo" },
  { value: "audit", label: "Audit" },
] as const;

type TabName = (typeof TABS)[number]["value"];

function isTab(v: string | null): v is TabName {
  return TABS.some((t) => t.value === v);
}

function TabBody({ tab, c, onUpdated, docKind, setDocKind }: { tab: TabName; c: Case; onUpdated: (c: Case) => void; docKind: DocKind; setDocKind: (k: DocKind) => void }) {
  switch (tab) {
    case "decision":
      return <DecisionTab c={c} onUpdated={onUpdated} />;
    case "documents":
      return <DocumentsTab c={c} />;
    case "bank":
      return <BankTab c={c} />;
    case "eligibility":
      return <EligibilityTab c={c} />;
    case "risk":
      return <RiskTab c={c} />;
    case "capacity":
      return <CapacityTab c={c} />;
    case "fraud":
      return <FraudTab c={c} />;
    case "rules":
      return <RulesTab c={c} />;
    case "memo":
      return <MemoTab c={c} kind={docKind} onKind={setDocKind} />;
    case "audit":
      return <AuditTab c={c} />;
  }
}

export default function CaseDetail() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const q = params.get("tab");
  const tab: TabName = isTab(q) ? q : "decision";
  const docKind: DocKind = params.get("doc") === "letter" ? "letter" : "memo";
  const res = useAsync(() => api.getCase(id), id);

  function go(next: string) {
    if (next === "memo:letter") setParams({ tab: "memo", doc: "letter" }, { replace: true });
    else setParams(next === "decision" ? {} : { tab: next }, { replace: true });
  }

  if (res.error) return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data) return <PageSkeleton />;
  const c = res.data;

  return (
    <div className="space-y-4">
      <Link to="/pipeline" className="no-print inline-flex items-center gap-1.5 text-sm text-graphite hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Pipeline
      </Link>
      <div className="no-print space-y-4">
        <CaseHeader c={c} onTab={go} />
        <DecisionHero c={c} />
        <Segmented<TabName>
          ariaLabel="Case sections"
          value={tab}
          onChange={go}
          items={TABS.map((t) => ({ value: t.value, label: t.label, testId: `tab-${t.value}` }))}
        />
      </div>
      <div role="tabpanel" aria-label={TABS.find((t) => t.value === tab)?.label}>
        <TabBody tab={tab} c={c} onUpdated={res.setData} docKind={docKind} setDocKind={(k) => setParams(k === "letter" ? { tab: "memo", doc: "letter" } : { tab: "memo" }, { replace: true })} />
      </div>
    </div>
  );
}
