import { expect, test } from "@playwright/test";

/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — dedicated source-health hash route.
 * UI ≠ canonical. SOURCE HEALTH ≠ authority. UNKNOWN ≠ healthy.
 */

const SOURCE_HEALTH = "/#/source-health";

test.describe("Atlas Web — source health (AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001)", () => {
  test("Source health (#/source-health) requires explicit project and stays non-authority", async ({
    page,
  }) => {
    await page.goto(SOURCE_HEALTH);
    await expect(page.getByRole("heading", { level: 1, name: "Source health" })).toBeVisible();
    await expect(page.getByText("ui_canonical=false").first()).toBeVisible();
    await expect(page.getByText("source_health≠authority")).toBeVisible();
    await expect(page.getByText("unknown≠healthy")).toBeVisible();
    await expect(
      page.getByText("UNKNOWN — select a project. No implicit portfolio-all."),
    ).toBeVisible();
  });
});
