import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

/**
 * Smoke e2e for NOVA Persian home → start analysis.
 *
 * Default: live web against local FastAPI (PROVIDER_MODE=stub).
 * Fixture-only: E2E_DATA_SOURCE=mock npm run test:e2e
 *
 * Env:
 *   E2E_BASE_URL          default http://127.0.0.1:3000
 *   E2E_API_URL           default http://127.0.0.1:8000
 *   E2E_DATA_SOURCE       live | mock (default live)
 *   E2E_SKIP_WEBSERVER    1 to reuse already-running servers
 */

const dataSource = (process.env.E2E_DATA_SOURCE || "live").toLowerCase();
const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";
const apiURL = process.env.E2E_API_URL || "http://127.0.0.1:8000";
const skipWebServer = process.env.E2E_SKIP_WEBSERVER === "1";
const apiDir = path.resolve(__dirname, "../api");

const webServers = skipWebServer
  ? undefined
  : dataSource === "mock"
    ? [
        {
          command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            NEXT_PUBLIC_DATA_SOURCE: "mock",
          },
        },
      ]
    : [
        {
          command:
            "PROVIDER_MODE=stub python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
          cwd: apiDir,
          url: `${apiURL}/api/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            PROVIDER_MODE: "stub",
            ADMIN_USERNAME: "admin",
            ADMIN_PASSWORD: "nova-dev-change-me",
          },
        },
        {
          command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            NEXT_PUBLIC_DATA_SOURCE: "live",
            NEXT_PUBLIC_API_BASE_URL: apiURL,
          },
        },
      ];

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  timeout: 90_000,
  use: {
    baseURL,
    trace: "on-first-retry",
    locale: "fa-IR",
    ...devices["Desktop Chrome"],
  },
  webServer: webServers,
});
