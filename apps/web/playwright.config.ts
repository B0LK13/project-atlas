import { defineConfig, devices } from "@playwright/test";

/**
 * AS-WEB-BROWSER-E2E-001 — repository-native browser acceptance for apps/web.
 *
 * This config automates the operator journey that was first captured only as
 * manual observational evidence (Hub → Projects → Mission Control LIVE→DEMO →
 * design-lab). BROWSER_E2E is PASS only when this reproducible suite is green.
 *
 * The Vite dev server is started/reused on the fixed strictPort (5173) declared
 * in vite.config.ts. UI ≠ canonical: these are read-only presentation checks.
 */
const PORT = 5173;
const BASE_URL = `http://localhost:${PORT}`;

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
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
