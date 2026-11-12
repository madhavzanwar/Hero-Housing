// Records the FinPilot HomeLoan demo walkthrough with Playwright.
// Usage: node scripts/video/record.mjs   (backend on :8000, frontend on :5173)
// Writes <WORK>/raw/*.webm and <WORK>/timeline.json (scene offsets in ms since recording start).
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const require = createRequire(import.meta.url);
let playwright;
try {
  playwright = require("playwright");
} catch {
  playwright = require(path.join(execSync("npm root -g").toString().trim(), "playwright"));
}
const { chromium } = playwright;

const BASE = process.env.APP_URL ?? "http://localhost:5173";
const API = process.env.API_URL ?? "http://localhost:8000";
const WORK = process.env.VIDEO_WORK ?? "/tmp/claude-0/video";
const W = 1600, H = 900;
const HOLD_PAD = 600;

const durations = JSON.parse(fs.readFileSync(path.join(WORK, "durations.json"), "utf8"));
const rawDir = path.join(WORK, "raw");
fs.rmSync(rawDir, { recursive: true, force: true });
fs.mkdirSync(rawDir, { recursive: true });

await fetch(`${API}/api/demo/reset`, { method: "POST" }).catch(() => {});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Visible cursor + click ripple (headless video does not render the OS cursor).
const CURSOR_JS = `
(() => {
  const install = () => {
    if (document.getElementById('__pw_cursor')) return;
    const c = document.createElement('div');
    c.id = '__pw_cursor';
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-2px);transition:transform 60ms';
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.5L9.5 19z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    const pos = window.__pwPos || {x: -100, y: -100};
    c.style.left = pos.x + 'px'; c.style.top = pos.y + 'px';
    document.addEventListener('mousemove', (e) => {
      window.__pwPos = {x: e.clientX, y: e.clientY};
      c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
    }, true);
    document.addEventListener('mousedown', (e) => {
      const r = document.createElement('div');
      r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;border-radius:50%;border:3px solid rgba(150,200,20,.95);background:rgba(198,241,53,.35);width:16px;height:16px;left:'+(e.clientX-8)+'px;top:'+(e.clientY-8)+'px;transition:all 450ms ease-out;opacity:1';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.width='56px'; r.style.height='56px'; r.style.left=(e.clientX-28)+'px'; r.style.top=(e.clientY-28)+'px'; r.style.opacity='0'; });
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();
`;

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: W, height: H },
  colorScheme: "light",
  recordVideo: { dir: rawDir, size: { width: W, height: H } },
});
await context.addInitScript(() => {
  try {
    localStorage.setItem("fphl:theme", "light");
  } catch {}
});
await context.addInitScript(CURSOR_JS);
const page = await context.newPage();
const t0 = Date.now();
const mouse = { x: W / 2, y: H / 2 };
const timeline = [];

async function moveTo(x, y, steps = 28) {
  await page.mouse.move(x, y, { steps });
  mouse.x = x;
  mouse.y = y;
}
async function moveToLoc(loc, steps = 28) {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (!b) throw new Error("no bbox");
  await moveTo(b.x + b.width / 2, b.y + b.height / 2, steps);
}
async function click(loc, pause = 300) {
  await moveToLoc(loc);
  await sleep(pause);
  await page.mouse.down();
  await sleep(70);
  await page.mouse.up();
  await sleep(250);
}
async function scroll(total, step = 40, delay = 28) {
  const n = Math.ceil(Math.abs(total) / step);
  for (let i = 0; i < n; i++) {
    await page.mouse.wheel(0, Math.sign(total) * step);
    await sleep(delay);
  }
}
/** Smoothly scroll until an element's top sits ~topPx from the viewport top. */
async function scrollTo(loc, topPx = 140) {
  await loc.waitFor({ state: "attached" });
  for (let i = 0; i < 200; i++) {
    const b = await loc.boundingBox();
    if (!b) break;
    const d = b.y - topPx;
    if (Math.abs(d) < 30) break;
    const before = await page.evaluate(() => window.scrollY + (document.querySelector("main")?.scrollTop ?? 0));
    await page.mouse.wheel(0, Math.sign(d) * Math.min(40, Math.abs(d)));
    await sleep(28);
    const after = await page.evaluate(() => window.scrollY + (document.querySelector("main")?.scrollTop ?? 0));
    if (before === after && i > 3) break; // at the end
  }
}
async function typeSlow(loc, text, delay = 55) {
  await click(loc, 150);
  await loc.pressSequentially(text, { delay });
}
async function scene(id, fn) {
  const start = Date.now() - t0;
  timeline.push({ id, start });
  console.log(`[${(start / 1000).toFixed(2)}s] scene ${id}`);
  await fn();
  const target = durations[id] * 1000 + HOLD_PAD;
  const spent = Date.now() - t0 - start;
  if (spent < target) await sleep(target - spent);
  else console.log(`  (scene ${id} overran by ${spent - target} ms)`);
  timeline[timeline.length - 1].end = Date.now() - t0;
}
const tid = (t) => page.getByTestId(t);

// ---- warm-up: load the landing page before the intro mark (trimmed later) ----
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await sleep(1200);
await moveTo(W * 0.62, H * 0.45, 5);
await sleep(300);

await scene("intro", async () => {
  await sleep(1800);
  await moveTo(W * 0.5, H * 0.55, 40);
  await scroll(500, 20, 45);
  await sleep(1500);
  await scroll(500, 20, 45);
  await sleep(1500);
  await scroll(-1000, 50, 25);
  await moveToLoc(tid("nav-pipeline"), 40);
});

await scene("pipeline", async () => {
  await click(tid("nav-pipeline"));
  await page.waitForURL("**/pipeline");
  const rows = page.locator("tbody tr");
  await rows.first().waitFor();
  await sleep(1200);
  await scrollTo(page.locator("table").first(), 180);
  const n = Math.min(await rows.count(), 12);
  for (let i = 0; i < n; i++) {
    await moveToLoc(rows.nth(i), 14);
    await sleep(520);
  }
  await scroll(-1500, 60, 20);
  await moveToLoc(tid("new-case-button"), 30);
});

await scene("newcase", async () => {
  await click(tid("new-case-button"));
  await page.waitForURL("**/cases/new");
  const chip = tid("persona-chip-p05");
  await chip.waitFor();
  await sleep(700);
  await click(chip);
  await sleep(1000);
  await click(tid("load-persona-docs"));
  await page.locator('[data-testid="file-list"] li').first().waitFor();
  await sleep(300);
  await scrollTo(tid("file-list"), 200);
  const items = page.locator('[data-testid="file-list"] li');
  const n = await items.count();
  for (let i = 0; i < n; i += 2) {
    await moveToLoc(items.nth(i), 12);
    await sleep(350);
  }
  await moveToLoc(tid("run-underwriting"), 30);
});

let caseId = null;
await scene("graph", async () => {
  const sceneStart = Date.now();
  const releaseAt = sceneStart + durations.graph * 1000 - 2600;
  await page.route("**/api/cases", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const resp = await route.fetch();
    const body = await resp.body();
    const wait = releaseAt - Date.now();
    if (wait > 0) await sleep(wait);
    await route.fulfill({ response: resp, body });
  });
  await click(tid("run-underwriting"));
  await sleep(700);
  await moveTo(W * 0.5, H * 0.6, 30);
  await page.waitForURL(/\/cases\/(?!new)[^/?]+/, { timeout: 60000 });
  caseId = page.url().split("/cases/")[1].split("?")[0];
  await page.unroute("**/api/cases");
  await tid("decision-outcome").waitFor();
});
console.log("case", caseId);

await scene("decision", async () => {
  await sleep(1500);
  await moveTo(W * 0.55, H * 0.6, 30);
  await scrollTo(tid("decision-card"), 120);
  await sleep(1500);
  await scroll(450, 20, 50);
  await sleep(1200);
  const path = page.getByText("Path to approval").first();
  if (await path.count()) await scrollTo(path, 260);
  await sleep(800);
  await scroll(300, 20, 60);
});

await scene("documents", async () => {
  await scroll(-3000, 80, 15);
  await click(tid("tab-documents"));
  await sleep(1000);
  const docs = page.locator('ul[aria-label="Documents"] button');
  await docs.first().waitFor();
  const aadhaar = docs.filter({ hasText: /aadhaar/i }).first();
  await scrollTo(page.locator('ul[aria-label="Documents"]'), 120);
  if (await aadhaar.count()) await click(aadhaar);
  await sleep(2200);
  const slip = docs.filter({ hasText: /salary/i }).first();
  if (await slip.count()) await click(slip);
  await sleep(2200);
  await moveTo(W * 0.6, H * 0.6, 20);
  await scrollTo(page.getByText("Cross-document consistency").first(), 110);
  await sleep(600);
  await scroll(200, 20, 60);
});

await scene("risk", async () => {
  await scroll(-4000, 100, 12);
  await click(tid("tab-risk"));
  await sleep(1200);
  await moveTo(W * 0.6, H * 0.65, 20);
  await scroll(380, 20, 45);
  await sleep(2400);
  await scroll(-1000, 60, 15);
  await click(tid("tab-capacity"));
  await sleep(1200);
  await moveTo(W * 0.6, H * 0.65, 20);
  await scroll(380, 20, 45);
});

await scene("rules", async () => {
  await scroll(-3000, 100, 12);
  await click(tid("tab-rules"));
  await sleep(1200);
  await moveTo(W * 0.6, H * 0.65, 20);
  await scroll(400, 20, 50);
  await sleep(1500);
  await scroll(500, 20, 50);
});

await scene("copilot", async () => {
  await scroll(-4000, 100, 12);
  await click(page.getByRole("button", { name: /Ask Copilot/ }));
  const input = tid("copilot-input");
  await input.waitFor();
  await sleep(500);
  await typeSlow(input, "Why is this approved with conditions?", 50);
  await sleep(300);
  await click(tid("copilot-send"));
  await tid("copilot-answer").waitFor({ timeout: 30000 });
  await sleep(800);
  await moveToLoc(tid("copilot-answer"), 25);
  await scroll(300, 20, 60);
});

await scene("override", async () => {
  await page.keyboard.press("Escape");
  await sleep(500);
  if (await tid("copilot-input").isVisible().catch(() => false)) {
    const close = page.getByRole("button", { name: /close/i }).first();
    if (await close.count()) await click(close);
  }
  await click(tid("tab-decision"));
  await sleep(500);
  await scrollTo(page.getByText("Underwriter override").first(), 100);
  await click(tid("override-outcome-REFER"));
  await typeSlow(tid("override-underwriter"), "R. Iyer", 45);
  await typeSlow(tid("override-reason"), "Refer for co-applicant income proof before sanction.", 22);
  await click(tid("override-submit"));
  await sleep(1300);
  await scroll(-4000, 100, 12);
  await sleep(1000);
  await click(tid("tab-audit"));
  await sleep(600);
  await moveTo(W * 0.6, H * 0.65, 20);
  await scroll(250, 20, 50);
});

await scene("fraud", async () => {
  await page.goto(BASE + "/cases/DEMO-P07");
  await tid("decision-outcome").waitFor();
  await moveTo(W * 0.55, H * 0.55, 20);
  await sleep(1400);
  await scroll(350, 20, 45);
  await sleep(1800);
  await scroll(-1000, 60, 15);
  await click(tid("tab-fraud"));
  await sleep(1000);
  await moveTo(W * 0.6, H * 0.65, 20);
  await scroll(380, 20, 50);
});

await scene("outro", async () => {
  await click(page.locator('nav a[href$="/portfolio"]').first());
  await page.waitForURL("**/portfolio");
  await sleep(2400);
  await moveTo(W * 0.6, H * 0.6, 20);
  await scroll(300, 20, 50);
  await sleep(1500);
  await scroll(-600, 40, 20);
  await click(tid("theme-toggle"));
  await sleep(2500);
  await moveTo(W * 0.6, H * 0.6, 30);
});
await sleep(1500);
const total = Date.now() - t0;

await page.close();
await context.close();
await browser.close();
const vids = fs.readdirSync(rawDir).filter((f) => f.endsWith(".webm"));
fs.writeFileSync(
  path.join(WORK, "timeline.json"),
  JSON.stringify({ video: path.join(rawDir, vids[0]), total, caseId, scenes: timeline }, null, 1),
);
console.log("done", total, vids);
