import { expect, test } from "@playwright/test";
import a1 from "../src/data/test-fixtures/generated-a1-packet.json" with { type: "json" };
import journey from "../src/data/test-fixtures/mission-journey.json" with { type: "json" };

const base = "http://127.0.0.1:47631";

test("mission workspace connects knowledge to a safe lane inspection", async ({ page }) => {
  const journeyWithLane = structuredClone(journey);
  journeyWithLane.development.candidate_identity = { top_claim_lanes: [{ lane: "pr/123", action_class: "READONLY_ANALYZE" }] };
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ json: journeyWithLane }));
  await page.goto("/#/mission-control");
  await expect(page.getByRole("heading", { name: "Mission workspace" })).toBeVisible();
  await expect(page.getByText("ADR 035")).toBeVisible();
  await expect(page.getByText("These are supported external handoffs from the contract.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  const lane = page.getByLabel("Development lane");
  await expect(lane).toBeVisible();
  await expect(page.getByRole("button", { name: "Inspect task context" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /execute|resume/i })).toHaveCount(0);
});

test("mission journey failure stays explicit while A1 remains inspectable", async ({ page }) => {
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ status: 503, json: { reason: "MISSION_JOURNEY_OFFLINE" } }));
  await page.goto("/#/mission-control");
  await expect(page.getByRole("heading", { name: "Mission workspace unavailable" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  await expect(page.getByText("Mission Journey unavailable")).toBeVisible();
});
