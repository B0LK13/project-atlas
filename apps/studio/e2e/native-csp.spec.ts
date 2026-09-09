import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const config = JSON.parse(readFileSync(new URL("../src-tauri/tauri.conf.json", import.meta.url), "utf8"));

test("native production CSP permits startup without runtime code generation", async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.route("http://127.0.0.1:4420/", async route => {
    const response = await route.fetch();
    await route.fulfill({ response, headers: { ...response.headers(), "content-security-policy": config.app.security.csp } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Mission Control", exact: true })).toBeVisible();
  expect(failures).toEqual([]);
});
