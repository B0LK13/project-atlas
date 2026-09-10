import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { remote } from "webdriverio";
import fixturePacket from "../src/data/test-fixtures/generated-a1-packet.json" with { type: "json" };

const binary = process.env.STUDIO_NATIVE_BINARY ?? path.resolve("src-tauri/target/release/atlas-studio");
const driverPort = Number(process.env.STUDIO_NATIVE_DRIVER_PORT ?? 4444);
const evidenceDir = path.resolve(process.env.STUDIO_NATIVE_EVIDENCE_DIR ?? "artifacts/native");
const sourceLabel = process.env.STUDIO_NATIVE_SOURCE ?? "unspecified";
const fixtureMode = sourceLabel === "fixture";

function fixtureServer() {
  const state = { mode: "normal" };
  const server = http.createServer((request, response) => {
    if (!request.url?.startsWith("/v1/mission-control")) { response.writeHead(404); response.end(); return; }
    response.setHeader("Access-Control-Allow-Origin", "tauri://localhost");
    if (state.mode === "malformed") { response.writeHead(200, { "Content-Type": "application/json" }); response.end("{malformed"); return; }
    if (state.mode === "incomplete") { response.writeHead(200, { "Content-Type": "application/json" }); response.end("{}"); return; }
    const packet = structuredClone(fixturePacket);
    if (state.mode === "changed") packet.attention[0].detail = "Updated fixture detail after refresh.";
    if (state.mode === "removed") packet.attention = packet.attention.slice(1);
    if (state.mode === "stale") { packet.freshness.state = "STALE"; packet.freshness.age_seconds = 900; }
    response.writeHead(200, { "Content-Type": "application/json" }); response.end(JSON.stringify(packet));
  });
  return { state, server };
}

fs.mkdirSync(evidenceDir, { recursive: true });
let fixture;
if (fixtureMode) {
  fixture = fixtureServer();
  await new Promise((resolve, reject) => { fixture.server.once("error", reject); fixture.server.listen(47631, "127.0.0.1", resolve); });
}
let browser;
try {
  browser = await remote({
    hostname: "127.0.0.1",
    port: driverPort,
    logLevel: "error",
    capabilities: {
      browserName: "wry",
      "wdio:enforceWebDriverClassic": true,
      "tauri:options": { application: binary },
    },
  });
  console.log(`source=${sourceLabel}`);
  console.log(`binary=${binary}`);
  console.log(`session=${browser.sessionId}`);
  console.log(`title=${await browser.getTitle()}`);
  await (await browser.$("h1")).waitForExist({ timeout: 20_000 });
  console.log(`heading=${await (await browser.$("h1")).getText()}`);

  const filter = await browser.$('input[placeholder="Search IDs, titles, causes"]');
  await filter.waitForExist({ timeout: 20_000 });
  await filter.click();
  await browser.keys(["TAB"]);
  const focus = await browser.execute(() => ({ tag: document.activeElement?.tagName, id: (document.activeElement instanceof HTMLElement) ? document.activeElement.id : "" }));
  console.log(`keyboard_focus=${JSON.stringify(focus)}`);
  await filter.setValue("EXTERNAL_IV_GATED");
  console.log(`filter=${await filter.getValue()}`);

  const option = await browser.$('[role="option"]');
  await option.waitForExist({ timeout: 5_000 });
  await option.click();
  const detail = await browser.$(".attention-detail-primary");
  await detail.waitForExist({ timeout: 5_000 });
  console.log(`selected=${await detail.getText()}`);
  const detailBody = await browser.$(".attention-detail-content > p:not(.attention-detail-primary)");
  const initialDetail = await detailBody.getText();

  const inspect = await browser.$("a.attention-inspect-link");
  await inspect.click();
  await browser.$("h1").waitForExist({ timeout: 5_000 });
  console.log(`secondary=${await (await browser.$("h1")).getText()}`);
  const returnLink = await browser.$('a[href="#/mission-control"]');
  await returnLink.click();
  await browser.$('input[placeholder="Search IDs, titles, causes"]').waitForExist({ timeout: 5_000 });
  console.log(`returned=${await (await browser.$("h1")).getText()}`);

  if (fixtureMode) {
    fixture.state.mode = "changed";
    await (await browser.$('button[aria-label="Refresh read-only projection"]')).click();
    await browser.waitUntil(async () => (await detailBody.getText()) !== initialDetail, { timeout: 10_000 });
    console.log(`refresh_changed=${await detailBody.getText()}`);
    fixture.state.mode = "removed";
    await (await browser.$('button[aria-label="Refresh read-only projection"]')).click();
    await (await browser.$("body")).waitForExist({ timeout: 2_000 });
    console.log(`removed_notice=${(await browser.getPageSource()).includes("no longer in this projection")}`);
    fixture.state.mode = "stale";
    await (await browser.$('button[aria-label="Refresh read-only projection"]')).click();
    await browser.waitUntil(async () => (await browser.getPageSource()).includes("STALE READ-ONLY PROJECTION"), { timeout: 10_000 });
    console.log("stale_state=true");
    fixture.state.mode = "malformed";
    await (await browser.$('button[aria-label="Refresh read-only projection"]')).click();
    await browser.waitUntil(async () => (await browser.getPageSource()).includes("Projection unavailable"), { timeout: 10_000 });
    console.log("malformed_state=true");
    fixture.state.mode = "normal";
    await (await browser.$('button[aria-label="Refresh read-only projection"]')).click();
    await browser.waitUntil(async () => (await browser.getPageSource()).includes("Your attention is needed"), { timeout: 10_000 });
    console.log("recovered_state=true");
  }

  const screenshotResponse = await fetch(`http://127.0.0.1:${driverPort}/session/${browser.sessionId}/screenshot`);
  if (!screenshotResponse.ok) throw new Error(`webdriver screenshot failed: HTTP ${screenshotResponse.status}`);
  const screenshot = await screenshotResponse.json();
  const screenshotPath = path.join(evidenceDir, "mission-control-filter.png");
  fs.writeFileSync(screenshotPath, Buffer.from(screenshot.value, "base64"));
  console.log(`screenshot=${screenshotPath}`);
} finally {
  if (browser) await browser.deleteSession();
  if (fixture) await new Promise((resolve) => fixture.server.close(resolve));
}
