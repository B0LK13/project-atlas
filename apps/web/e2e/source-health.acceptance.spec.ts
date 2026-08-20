import { expect, test } from "@playwright/test";

/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — honest LIVE failure, no silent invent.
 * UI ≠ canonical. SOURCE HEALTH ≠ AUTHORITY. UNKNOWN remains UNKNOWN.
 *
 * Authentic browser/Playwright is required for visual certification.
 * Node contract smoke covers cloud-safe wiring only.
 */

const SOURCE_HEALTH = "/#/source-health";
const SCOPED = "/#/source-health?project=harbor-api";

test.describe("Atlas Web — source health (AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001)", () => {
  test("unscoped page requires explicit project and stays UNKNOWN", async ({
    page,
  }) => {
    await page.goto(SOURCE_HEALTH);
    await expect(
      page.getByRole("heading", { level: 1, name: "Source health" }),
    ).toBeVisible();
    await expect(page.getByText("ui_canonical=false").first()).toBeVisible();
    await expect(page.getByText("source_health≠authority")).toBeVisible();
    await expect(page.getByText("score_theatre=false")).toBeVisible();
    await expect(page.getByText("write_controls=false")).toBeVisible();
    await expect(
      page.getByText(/UNKNOWN — explicit project required/),
    ).toBeVisible();
    await expect(page.getByText("SOURCE HEALTH != AUTHORITY").first()).toBeVisible();
  });

  test("scoped LIVE failure is visible and not replaced by a live-labelled demo", async ({
    page,
  }) => {
    await page.goto(SCOPED);
    await expect(
      page.getByRole("heading", { level: 1, name: "Source health" }),
    ).toBeVisible();
    const failure = page.getByText(/Source health unavailable:/);
    await expect(failure).toBeVisible();
    await expect(failure).toContainText("not replaced");
    await expect(page.getByText(/DEGRADED \/ UNAVAILABLE/)).toBeVisible();
    await expect(page.getByText("data_source=live_api")).toHaveCount(0);
  });
});
