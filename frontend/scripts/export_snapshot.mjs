#!/usr/bin/env node
/**
 * Export a static demo snapshot from a running FinPilot HomeLoan backend.
 *
 *   node scripts/export_snapshot.mjs [--api http://127.0.0.1:8000] [--no-docs]
 *
 * Writes:
 *   src/demo/snapshot.json            cases (full CaseDetail), personas, persona details,
 *                                     portfolio, policy, model card, memos and outcome letters
 *   public/demo-docs/<case>/<doc_id>  original document bytes for the document viewer
 *
 * The frontend falls back to this snapshot when the backend is unreachable or VITE_DEMO=1.
 */
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const apiArg = args.indexOf("--api");
const API = (apiArg >= 0 ? args[apiArg + 1] : process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const withDocs = !args.includes("--no-docs");

async function get(p, kind = "json") {
  const res = await fetch(`${API}/api${p}`);
  if (!res.ok) throw new Error(`GET ${p} -> ${res.status} ${await res.text()}`);
  if (kind === "json") return res.json();
  if (kind === "text") return res.text();
  return Buffer.from(await res.arrayBuffer());
}

async function main() {
  console.log(`Exporting snapshot from ${API}`);
  const health = await get("/health");
  const preload = health.preload ?? {};
  if (preload.state === "running") console.warn(`warning: persona preload still running (${preload.done}/${preload.total})`);

  const summaries = await get("/cases");
  const personas = await get("/personas");
  const cases = [];
  const memos = {};
  const letters = {};
  for (const s of summaries) {
    const c = await get(`/cases/${encodeURIComponent(s.id)}`);
    cases.push(c);
    memos[c.id] = await get(`/cases/${encodeURIComponent(c.id)}/memo`, "text").catch(() => c.memo_markdown);
    letters[c.id] = await get(`/cases/${encodeURIComponent(c.id)}/sanction-letter`, "text").catch(() => undefined);
    process.stdout.write(`  case ${c.id} (${c.persona_id ?? "-"}) ${c.decision.outcome}\n`);
  }
  const persona_details = [];
  for (const p of personas) persona_details.push(await get(`/personas/${encodeURIComponent(p.id)}`));

  const snapshot = {
    generated_at: new Date().toISOString(),
    source: API,
    cases,
    personas,
    persona_details,
    portfolio: await get("/portfolio"),
    policy: await get("/policy"),
    model_card: await get("/model-card"),
    memos,
    letters,
  };
  const out = path.join(root, "src/demo/snapshot.json");
  await mkdir(path.dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(snapshot));
  console.log(`wrote ${out} (${cases.length} cases, ${(JSON.stringify(snapshot).length / 1024).toFixed(0)} KB)`);

  if (withDocs) {
    const docsDir = path.join(root, "public/demo-docs");
    await rm(docsDir, { recursive: true, force: true });
    let n = 0;
    for (const c of cases) {
      for (const d of c.bundle.documents) {
        try {
          const bytes = await get(`/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(d.id)}`, "bytes");
          const f = path.join(docsDir, c.id, d.id);
          await mkdir(path.dirname(f), { recursive: true });
          await writeFile(f, bytes);
          n++;
        } catch (e) {
          console.warn(`  skip ${c.id}/${d.id}: ${e.message}`);
        }
      }
    }
    console.log(`wrote ${n} documents to ${docsDir}`);
  }
}

main().catch((e) => {
  console.error(e.message ?? e);
  process.exit(1);
});
