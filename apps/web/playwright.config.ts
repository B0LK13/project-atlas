import { defineConfig, devices } from "@playwright/test";

/**
 * AS-WEB-BROWSER-E2E-001 — repository-native browser acceptance for apps/web.
 *
 * This config automates the operator journey that was first captured only as
 * manual observational evidence (Hub → Projects → Mission Control LIVE→DEMO →
 * design-lab). BROWSER_E2E is PASS only when this reproducible suite is green.
 *
 * Default webServer uses `vite preview` on port 4173 (override with
 * PLAYWRIGHT_WEB_PORT). Preview avoids Windows Hyper-V / excluded TCP ranges
 * that commonly block Vite's default :5173 (listen EACCES). UI ≠ canonical:
 * these are read-only presentation checks against a built `dist/`.
 */
const PORT = Number(process.env.PLAYWRIGHT_WEB_PORT ?? "4173");
const HOST = process.env.PLAYWRIGHT_WEB_HOST ?? "127.0.0.1";
const BASE_URL = `http://${HOST}:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Opt-in browser video capture (PW_VIDEO=1) for walkthrough evidence.
    video: process.env.PW_VIDEO ? "on" : "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Build then preview so the suite does not depend on Vite's :5173
    // strictPort (blocked on some Windows IV hosts).
    command: `npm run build && npx vite preview --host ${HOST} --port ${PORT} --strictPort`,
    url: BASE_URL,
    // SEC-030: never reuse a foreign/stale server — suite must own the listener.
    // Escape hatch (unsafe): ATLAS_PW_REUSE=1 for local debugging only.
    reuseExistingServer: process.env.ATLAS_PW_REUSE === "1",
    timeout: 180_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
