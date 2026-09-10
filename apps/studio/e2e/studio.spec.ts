import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("http://127.0.0.1:47631/**", route => route.fulfill({ status: 503, body: "{}" }));
});

test("unavailable state and palette focus restoration", async ({ page }) => {
  await page.goto("/#/mission-control");
  await expect(page.getByRole("heading", { name: "Projection unavailable" })).toBeVisible();
  await expect(page.getByRole("status")).not.toContainText("FIXTURE");
  const trigger = page.getByRole("button", { name: /Navigate Studio screens/ });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const input = page.getByRole("textbox", { name: "Search read-only Studio destinations" });
  await expect(input).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("dialog").getByRole("button").last()).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Enter");
  await input.fill("verification");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/verification$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("same-screen hash, direct link, reload and history", async ({ page }) => {
  await page.goto("/#/design-lab/orbital");
  const orbital = await page.locator("main").innerText();
  await page.evaluate(() => { location.hash = "/design-lab/workbench"; });
  await expect(page.locator("main")).not.toHaveText(orbital, { useInnerText: true });
  const workbench = await page.locator("main").innerText();
  await page.reload();
  await expect(page.locator("main")).toHaveText(workbench, { useInnerText: true });
  await page.goBack();
  await expect(page).toHaveURL(/orbital$/);
  await expect(page.locator("main")).toHaveText(orbital, { useInnerText: true });
  await page.goForward();
  await expect(page).toHaveURL(/workbench$/);
  await expect(page.locator("main")).toHaveText(workbench, { useInnerText: true });
});

for (const [width, height] of [[980, 700], [1366, 768], [1920, 1080]]) {
  test(`essential controls fit ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height });
    await page.goto("/#/mission-control");
    await expect(page.getByRole("heading", { name: "Projection unavailable" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh read-only projection" })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("viewport.png"), fullPage: false });
  });
}
