import { defineConfig } from "@playwright/test";

// Starts the FastAPI backend and the Vite dev server unless E2E_BASE_URL points at a running deployment.
const external = process.env.E2E_BASE_URL;
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "results.json" }]],
  use: {
    baseURL: external ?? "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
    trace: "off",
  },
  webServer: external
    ? undefined
    : [
        {
          command: `${python} -m uvicorn app.main:app --port 8000`,
          cwd: "../backend",
          url: "http://127.0.0.1:8000/api/health",
          reuseExistingServer: true,
          timeout: 120_000,
        },
        {
          command: "npm run dev -- --host 127.0.0.1 --port 5173",
          cwd: "../frontend",
          url: "http://127.0.0.1:5173",
          reuseExistingServer: true,
          timeout: 120_000,
        },
      ],
});
