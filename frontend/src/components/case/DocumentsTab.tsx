import { Check, ExternalLink, FileImage, FileText, FileWarning, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DOC_LABEL } from "@/lib/labels";
import type { CaseDetail, DocumentResult, Json } from "@/lib/types";
import { cn, humanize, isRecord } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { EmptyState } from "@/components/ui/EmptyState";
import { SeverityChip } from "@/components/ui/Badges";
import { Label, Mono } from "@/components/ui/misc";

function display(v: Json | unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-IN") : v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.map(display).join(", ");
  if (isRecord(v)) return Object.entries(v).map(([k, x]) => `${k}: ${display(x)}`).join("; ");
  return String(v);
}

type ViewState = { kind: "loading" } | { kind: "ok"; url: string; mime: string } | { kind: "missing" };

function DocViewer({ caseId, doc }: { caseId: string; doc: DocumentResult }) {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const src = api.documentUrl(caseId, doc.id);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;
    setState({ kind: "loading" });
    fetch(src)
      .then(async (res) => {
        const type = res.headers.get("content-type") ?? "";
        // A missing static file comes back as the SPA's index.html.
        if (!res.ok || type.includes("text/html")) throw new Error("missing");
        const blob = await res.blob();
        const typed = blob.type && blob.type !== "application/octet-stream" ? blob : new Blob([blob], { type: doc.mime_type });
        objectUrl = URL.createObjectURL(typed);
        if (alive) setState({ kind: "ok", url: objectUrl, mime: typed.type || doc.mime_type });
      })
      .catch(() => {
        if (alive) setState({ kind: "missing" });
      });
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src, doc.mime_type]);

  return (
    <div className="flex h-full min-h-[480px] flex-col overflow-hidden rounded-surface border border-hairline bg-fog">
      <div className="flex items-center justify-between gap-2 border-b border-hairline bg-paper px-3 py-2">
        <p className="truncate text-xs font-medium text-ink">{doc.filename}</p>
        <a href={state.kind === "ok" ? state.url : src} target="_blank" rel="noreferrer" className="flex shrink-0 items-center gap-1 text-xs text-graphite hover:text-ink">
          Open <ExternalLink className="size-3" aria-hidden />
        </a>
      </div>
      <div className="relative flex-1">
        {state.kind === "loading" && <div className="absolute inset-0 animate-skeleton-pulse bg-paper/60" aria-label="Loading document" />}
        {state.kind === "ok" &&
          (state.mime.startsWith("image/") ? (
            <div className="flex h-full items-start justify-center overflow-auto bg-[#e9ebe3] p-4">
              <img src={state.url} alt={`${DOC_LABEL[doc.doc_type]}: ${doc.filename}`} className="max-h-[640px] w-auto rounded-md bg-white shadow-md" />
            </div>
          ) : (
            <object data={state.url} type="application/pdf" className="absolute inset-0 size-full" aria-label={doc.filename}>
              <iframe src={state.url} title={doc.filename} className="size-full" />
            </object>
          ))}
        {state.kind === "missing" && (
          <div className="p-4">
            <p className="mb-2 flex items-center gap-1.5 text-xs text-pewter">
              <FileWarning className="size-3.5" aria-hidden /> Original file not available here. PII-masked text excerpt:
            </p>
            <pre className="whitespace-pre-wrap rounded-xl bg-paper p-3 font-mono text-[11px] leading-relaxed text-graphite">{doc.text_excerpt || "(no text)"}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

function DocList({ docs, selected, onSelect }: { docs: DocumentResult[]; selected: string; onSelect: (id: string) => void }) {
  return (
    <ul className="space-y-1.5" aria-label="Documents">
      {docs.map((d) => {
        const active = d.id === selected;
        const Icon = d.mime_type.includes("pdf") ? FileText : FileImage;
        return (
          <li key={d.id}>
            <button
              type="button"
              onClick={() => onSelect(d.id)}
              aria-current={active ? "true" : undefined}
              className={cn(
                "flex w-full items-start gap-2.5 rounded-surface border px-3 py-2.5 text-left transition-colors",
                active ? "border-lime-dark bg-tint-lime" : "border-transparent bg-fog hover:border-mist",
              )}
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-graphite" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-ink">{DOC_LABEL[d.doc_type]}</span>
                <span className="block truncate text-[11px] text-pewter">{d.filename}</span>
                <span className="mt-1 flex flex-wrap gap-1">
                  <Chip tone="outline" className="px-1.5 py-0 text-[10px]">
                    {d.ocr_engine}
                  </Chip>
                  {d.flags.length > 0 && (
                    <Chip tone="danger" className="px-1.5 py-0 text-[10px]">
                      {d.flags.length} flag{d.flags.length > 1 ? "s" : ""}
                    </Chip>
                  )}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function FieldsTable({ doc }: { doc: DocumentResult }) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Chip tone="lime">{DOC_LABEL[doc.doc_type]}</Chip>
        <ConfidenceChip value={doc.classification_confidence} label="class." />
        <span className="text-[11px] text-pewter">{doc.pages} page{doc.pages > 1 ? "s" : ""}</span>
      </div>
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-xs text-graphite">
            <th className="py-1.5 pr-2 font-medium">Field</th>
            <th className="py-1.5 pr-2 font-medium">Value</th>
            <th className="py-1.5 font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {doc.fields.map((f) => (
            <tr key={f.name} className="border-t border-hairline align-top">
              <td className="py-2 pr-2 text-graphite">{humanize(f.name)}</td>
              <td className="max-w-[180px] break-words py-2 pr-2 font-medium text-ink tnum">{display(f.value)}</td>
              <td className="py-2">
                <ConfidenceChip value={f.confidence} label="" />
                <span className="ml-1 block text-[10px] text-pewter">{f.source}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {doc.flags.length > 0 && (
        <div className="mt-3 space-y-2">
          {doc.flags.map((f) => (
            <div key={f.code} className="rounded-surface border border-bad-solid/20 bg-bad-soft p-3">
              <div className="flex items-center gap-2">
                <SeverityChip severity={f.severity} />
                <span className="text-sm font-semibold text-ink">{f.title}</span>
              </div>
              <p className="mt-1 text-xs text-graphite">{f.detail}</p>
            </div>
          ))}
        </div>
      )}
      {Object.keys(doc.metadata).length > 0 && (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer text-graphite">File metadata (producer, dates, fonts)</summary>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {Object.entries(doc.metadata)
              .filter(([k]) => !["sha256"].includes(k))
              .map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-pewter">{k}</dt>
                  <dd className="break-all font-mono text-[11px] text-ink">{display(v)}</dd>
                </div>
              ))}
          </dl>
          <p className="mt-2 text-pewter">
            SHA-256 <Mono>{doc.sha256.slice(0, 16)}…</Mono>
          </p>
        </details>
      )}
    </div>
  );
}

function CrossChecks({ c }: { c: CaseDetail }) {
  return (
    <Card>
      <CardHeader title="Cross-document consistency" subtitle="Each fact as seen on every document that carries it" />
      <div className="-mx-4 overflow-x-auto sm:-mx-5">
        <table className="w-full min-w-[760px] text-[13px]">
          <thead>
            <tr className="text-left text-xs text-graphite">
              <th className="px-5 py-2 font-medium">Check</th>
              <th className="px-3 py-2 font-medium">Values seen</th>
              <th className="px-3 py-2 font-medium">Similarity</th>
              <th className="px-5 py-2 font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {c.bundle.cross_checks.map((x) => (
              <tr key={x.field} className="border-t border-hairline align-top">
                <td className="px-5 py-3 font-semibold text-ink">{humanize(x.field)}</td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(x.values).map(([k, v]) => (
                      <span key={k} className="max-w-[260px] truncate rounded-lg bg-fog px-2 py-1 text-xs" title={`${k}: ${display(v)}`}>
                        <span className="text-pewter">{humanize(k)}:</span> <span className="text-ink tnum">{display(v)}</span>
                      </span>
                    ))}
                  </div>
                  {x.note && <p className="mt-1.5 text-xs text-graphite">{x.note}</p>}
                </td>
                <td className="px-3 py-3 text-ink tnum">{Math.round(x.score * 100)}%</td>
                <td className="px-5 py-3">
                  {x.match ? (
                    <Chip tone="success">
                      <Check className="size-3" aria-hidden /> Match
                    </Chip>
                  ) : (
                    <Chip tone="danger">
                      <X className="size-3" aria-hidden /> Mismatch
                    </Chip>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {c.bundle.missing_documents.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-surface bg-warn-soft p-3 text-sm">
          <span className="font-semibold text-warn">Missing documents:</span>
          {c.bundle.missing_documents.map((d) => (
            <Chip key={d} tone="warning">
              {DOC_LABEL[d]}
            </Chip>
          ))}
        </div>
      )}
    </Card>
  );
}

export function DocumentsTab({ c }: { c: CaseDetail }) {
  const docs = c.bundle.documents;
  const [selected, setSelected] = useState(docs[0]?.id ?? "");
  const doc = docs.find((d) => d.id === selected);
  if (!docs.length) return <EmptyState icon={FileWarning} title="No documents on this case" />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-3">
          <Label className="mb-3 block">{docs.length} documents</Label>
          <DocList docs={docs} selected={selected} onSelect={setSelected} />
        </Card>
        <Card className="lg:col-span-5">{doc && <DocViewer caseId={c.id} doc={doc} />}</Card>
        <Card className="lg:col-span-4">
          <CardHeader title="Extracted fields" subtitle="PII masked at read time" display={false} />
          {doc && <FieldsTable doc={doc} />}
        </Card>
      </div>
      <CrossChecks c={c} />
    </div>
  );
}
