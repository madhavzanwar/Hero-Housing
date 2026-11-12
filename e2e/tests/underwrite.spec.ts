import { test, expect } from "@playwright/test";

/**
 * End-to-end: RM uploads a synthetic persona's documents → engine decides → underwriter overrides with a reason.
 * Persona p05 (salaried, FOIR breach) is expected to come back APPROVE_WITH_CONDITIONS.
 */
test("upload persona documents → decision → underwriter override", async ({ page }) => {
  await page.goto("/pipeline");
  await page.getByTestId("new-case-button").click();

  // Quick-fill the application form from persona p05, then pull its document pack into the upload list.
  await page.getByTestId("persona-chip-p05").click();
  await page.getByTestId("load-persona-docs").click();
  await expect(page.getByTestId("file-list")).toContainText(/bank/i);
  const files = page.getByTestId("file-list").locator("li");
  await expect(files).not.toHaveCount(0);

  await page.getByTestId("run-underwriting").click();

  // Decision card renders with an explainable outcome.
  const outcome = page.getByTestId("decision-outcome");
  await expect(outcome).toBeVisible({ timeout: 90_000 });
  const engineOutcome = (await outcome.textContent())?.trim() ?? "";
  expect(["APPROVE", "APPROVE_WITH_CONDITIONS", "REFER", "DECLINE"]).toContain(engineOutcome);
  expect(engineOutcome).toBe("APPROVE_WITH_CONDITIONS");
  await expect(page.getByTestId("decision-card")).toContainText(/FOIR|reduce|co-applicant/i);

  // Rules fired tab cites policy rule IDs.
  await page.getByTestId("tab-rules").click();
  await expect(page.getByText(/ELG-FOIR-0\d/).first()).toBeVisible();

  // Underwriter override with a mandatory reason.
  await page.getByTestId("tab-decision").click();
  await page.getByTestId("override-outcome-REFER").click();
  await page.getByTestId("override-underwriter").fill("A. Underwriter");
  await page.getByTestId("override-reason").fill("Employer confirmation pending; refer to credit head for FOIR deviation.");
  await page.getByTestId("override-submit").click();

  await expect(page.getByTestId("case-status")).toContainText(/overridden/i);
  await expect(page.getByTestId("decision-outcome")).toHaveText("REFER");
});
