// Clean 1600x1000 @2x light-mode stills for the submission (separate from the video).
// Usage: node scripts/video/shots.mjs  -> submission/shots/*.png
import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const BASE = process.env.APP_URL ?? "http://localhost:5173";
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../submission/shots");
fs.mkdirSync(OUT, { recursive: true });
const CASE = process.env.SHOT_CASE ?? "DEMO-P05";
const FRAUD = process.env.SHOT_FRAUD_CASE ?? "DEMO-P07";

const browser = await pw.chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, colorScheme: "light" });
await ctx.addInitScript(() => { try { localStorage.setItem("fphl:theme", "light"); } catch {} });
const page = await ctx.newPage();
const settle = (ms = 1500) => page.waitForTimeout(ms);
const tabScroll = async () => {
  // bring the tab strip near the top so the tab body is in view
  await page.getByRole("tablist", { name: "Case sections" }).evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 90));
  await settle(700);
};
async function shot(name) { await page.screenshot({ path: path.join(OUT, name) }); console.log("wrote", name); }

await page.goto(`${BASE}/pipeline`, { waitUntil: "networkidle" });
await page.locator("tbody tr").first().waitFor(); await settle();
await shot("pipeline.png");

await page.goto(`${BASE}/cases/${CASE}`, { waitUntil: "networkidle" });
await page.getByTestId("decision-outcome").waitFor(); await settle();
await shot("case_decision.png");

await page.getByTestId("tab-documents").click(); await settle(); await tabScroll();
await shot("case_documents.png");

await page.getByTestId("tab-risk").click(); await settle(); await tabScroll();
await shot("case_risk.png");

await page.evaluate(() => window.scrollTo(0, 0));
await page.getByRole("button", { name: /Ask Copilot/ }).click();
await page.getByTestId("copilot-input").fill("Why is this approved with conditions?");
await page.getByTestId("copilot-send").click();
await page.getByTestId("copilot-answer").waitFor({ timeout: 30000 }); await settle();
await shot("copilot.png");

await page.goto(`${BASE}/cases/${FRAUD}?tab=fraud`, { waitUntil: "networkidle" });
await page.getByTestId("decision-outcome").waitFor(); await settle(); await tabScroll();
await shot("case_fraud.png");

await browser.close();
