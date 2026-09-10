import { expect, test } from "@playwright/test";
import a1 from "../src/data/test-fixtures/generated-a1-packet.json" with { type: "json" };

const base = "http://127.0.0.1:47631";

test("bounded decision queue supports keyboard detail and explicit disappearance", async ({ page }) => {
  const packets = [structuredClone(a1), structuredClone(a1), structuredClone(a1)];
  packets.forEach((packet, index) => {
    packet.attention = Array.from({ length: 118 }, (_, i) => ({
      ...a1.attention[i % a1.attention.length],
      attention_id: `queue-${i}`,
      kind: i < 60 ? "EXTERNAL_IV_GATED" : i < 95 ? "HUMAN_GATE" : "PANEL_STATUS",
      title: i < 60 ? "External IV gated / unbound" : i < 95 ? `Human gate action: pr/${793 + i}:OWNER_DECISION` : `View panel-${i} is UNKNOWN`,
      detail: `source record ${i}`,
    }));
    if (index === 2) packet.attention = packet.attention.filter((item) => item.attention_id !== "queue-0");
  });
  let removeSelected = false;
  await page.route(`${base}/v1/mission-control`, (route) => {
    const packet = removeSelected ? packets[2] : packets[0];
    return route.fulfill({ json: packet });
  });
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ status: 503, json: { reason: "MISSION_JOURNEY_OFFLINE" } }));
  await page.goto("/#/mission-control");
  await expect(page.getByText("118 attention items")).toBeVisible();
  await expect(page.getByRole("option", { name: /Independent verification unavailable/ })).toBeVisible();
  await expect(page.getByRole("option", { name: /Owner decisions/ })).toBeVisible();
  await expect(page.getByText("Inspect all 118 records")).toBeVisible();

  const first = page.getByRole("option").first();
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("source record 0")).toBeVisible();
  await page.getByRole("link", { name: "Inspect supported detail" }).click();
  await expect(page.getByRole("heading", { name: "verification", exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByText("source record 0")).toBeVisible();
  await page.reload();
  await expect(page.getByText("source record 0")).toBeVisible();
  await page.getByRole("button", { name: "Refresh read-only projection" }).click();
  await expect(page.getByText("source record 0")).toBeVisible();
  removeSelected = true;
  await page.getByRole("button", { name: "Refresh read-only projection" }).click();
  await expect(page.getByText("The selected attention item (queue-0) is no longer in this projection.")).toBeVisible();
});

test("secondary routes keep global attention compact and lead with their purpose", async ({ page }) => {
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ status: 503, json: { reason: "MISSION_JOURNEY_OFFLINE" } }));
  await page.goto("/#/agents");
  await expect(page.getByRole("heading", { name: /Which agents are observed/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /attention items.*Mission Control/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your attention is needed" })).toHaveCount(0);
  await page.goto("/#/knowledge");
  await expect(page.getByRole("heading", { name: /What knowledge and provenance/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /attention items.*Mission Control/i })).toBeVisible();
});
