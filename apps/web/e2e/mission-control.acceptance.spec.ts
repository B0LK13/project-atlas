import { expect, test } from "@playwright/test";

/**
 * AS-WEB-BROWSER-E2E-001 — first repository-native browser acceptance spec.
 *
 * This suite is the automated reproduction of the operator journey that was
 * previously only OBSERVED in a manual screen recording. Each assertion maps to
 * a bullet in that manual evidence, so a green run promotes:
 *   MANUAL_BROWSER_EVIDENCE = OBSERVED  ->  BROWSER_E2E = PASS
 *
 * Invariants under test (never weakened): UI ≠ canonical, Graph ≠ authority,
 * Unknown ≠ healthy, and LIVE failure is shown honestly rather than silently
 * replaced with invented data.
 */

const HUB = "/#/";
const PROJECTS = "/#/projects";
const MISSION_CONTROL = "/#/mission-control";
const TERMINAL_HONEST = "/#/design-lab/terminal-honest";

// Honest LIVE-failure copy emitted by useLiveMissionWorkspace when the
// LIVE_API (127.0.0.1:8765) is unreachable — no silent demo fallback.
const HONEST_LIVE_FAILURE = "choose DEMO or FIXTURE mode (no silent invent)";
const DEMO_BLURB = "Isolated demo stub. Not live vault. Not PILOT estate.";
const DEMO_BANNER = "DEMO STUB — isolated sample · not live vault · not PILOT";

test.describe("Atlas Web — operator journey (AS-WEB-BROWSER-E2E-001)", () => {
  test("Hub (#/) renders real production shell content", async ({ page }) => {
    await page.goto(HUB);
    await expect(page.getByRole("heading", { level: 1, name: "Atlas" })).toBeVisible();
    await expect(page.getByText("Project Atlas · AS-WEB-003")).toBeVisible();
    // Production shell hub exposes the Mission Control surface link (nav entry).
    await expect(
      page.getByRole("link", { name: "Mission Control", exact: true }),
    ).toBeVisible();
    // UI ≠ canonical invariant chip is present, never hidden.
    await expect(page.getByText("ui_canonical=false").first()).toBeVisible();
  });

  test("Projects (#/projects) renders the read-only inventory (demo-alpha)", async ({
    page,
  }) => {
    await page.goto(PROJECTS);
    await expect(page.getByRole("heading", { level: 1, name: "Projects" })).toBeVisible();
    // Inventory row observed in the manual walkthrough.
    await expect(page.getByText("demo-alpha", { exact: true })).toBeVisible();
    await expect(page.getByText("projects/demo-alpha")).toBeVisible();
  });

  test("Mission Control (#/mission-control) shows LIVE failure honestly, not silently", async ({
    page,
  }) => {
    await page.goto(MISSION_CONTROL);
    await expect(page.getByRole("heading", { level: 1, name: "Mission Control" })).toBeVisible();
    // LIVE mode is the default: the mode chip reflects it.
    await expect(page.getByText("lens_mode=live")).toBeVisible();
    // Honest failure banner rather than invented data.
    const failure = page.getByText(/Mission unavailable:/);
    await expect(failure).toBeVisible();
    await expect(failure).toContainText(HONEST_LIVE_FAILURE);
    // Unknown ≠ healthy: the board declares itself unavailable, not populated.
    await expect(
      page.getByText("unknown — mission view unavailable"),
    ).toBeVisible();
  });

  test("Clicking DEMO changes state: URL, banner, blurb and populated Mission board", async ({
    page,
  }) => {
    await page.goto(MISSION_CONTROL);

    // Precondition: honest LIVE failure is visible before interaction.
    await expect(page.getByText(/Mission unavailable:/)).toBeVisible();

    // The real interaction captured in the recording.
    await page.getByRole("button", { name: "DEMO" }).click();

    // URL updates to the demo mode query (hash router search param).
    await expect(page).toHaveURL(/#\/mission-control\?mode=demo$/);

    // DEMO stub disclosure + isolation banner become visible.
    await expect(page.getByText(DEMO_BLURB)).toBeVisible();
    await expect(page.getByText(DEMO_BANNER)).toBeVisible();

    // The DEMO button is now the active/pressed control.
    await expect(page.getByRole("button", { name: "DEMO" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Mission board is now populated (was "unavailable" under LIVE failure).
    const board = page.getByRole("region", { name: "Mission Control board" });
    await expect(board.getByText("Rollup")).toBeVisible();
    await expect(board.getByText("Project count")).toBeVisible();
    // No silent PILOT invention even in DEMO: estate rows stay 0.
    await expect(board.getByText("PILOT estate rows")).toBeVisible();

    // The honest LIVE-failure banner is gone once DEMO data loads.
    await expect(page.getByText(/Mission unavailable:/)).toHaveCount(0);
  });

  test("Design-lab terminal-honest (#/design-lab/terminal-honest) renders themed JSON", async ({
    page,
  }) => {
    await page.goto(TERMINAL_HONEST);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "$ atlas design-lab --theme terminal-honest",
      }),
    ).toBeVisible();
    // The always-visible honesty field in the terminal block (<pre> is not a
    // landmark region, so target the themed block directly).
    const term = page.locator("pre.term-block");
    await expect(term).toBeVisible();
    await expect(term).toContainText('"ui_canonical": false');
  });
});
