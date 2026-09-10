import fs from "node:fs";
import path from "node:path";
import { remote } from "webdriverio";

const binary = process.env.STUDIO_NATIVE_BINARY ?? path.resolve("src-tauri/target/release/atlas-studio");
const driverPort = Number(process.env.STUDIO_NATIVE_DRIVER_PORT ?? 4444);
const evidenceDir = path.resolve(process.env.STUDIO_NATIVE_EVIDENCE_DIR ?? "artifacts/native");
const sourceLabel = process.env.STUDIO_NATIVE_SOURCE ?? "unspecified";

fs.mkdirSync(evidenceDir, { recursive: true });
const browser = await remote({
  hostname: "127.0.0.1",
  port: driverPort,
  logLevel: "error",
  capabilities: {
    browserName: "wry",
    "wdio:enforceWebDriverClassic": true,
    "tauri:options": { application: binary },
  },
});

try {
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

  const inspect = await browser.$("a.attention-inspect-link");
  await inspect.click();
  await browser.$("h1").waitForExist({ timeout: 5_000 });
  console.log(`secondary=${await (await browser.$("h1")).getText()}`);
  const returnLink = await browser.$('a[href="#/mission-control"]');
  await returnLink.click();
  await browser.$('input[placeholder="Search IDs, titles, causes"]').waitForExist({ timeout: 5_000 });
  console.log(`returned=${await (await browser.$("h1")).getText()}`);

  const screenshotResponse = await fetch(`http://127.0.0.1:${driverPort}/session/${browser.sessionId}/screenshot`);
  if (!screenshotResponse.ok) throw new Error(`webdriver screenshot failed: HTTP ${screenshotResponse.status}`);
  const screenshot = await screenshotResponse.json();
  const screenshotPath = path.join(evidenceDir, "mission-control-filter.png");
  fs.writeFileSync(screenshotPath, Buffer.from(screenshot.value, "base64"));
  console.log(`screenshot=${screenshotPath}`);
} finally {
  await browser.deleteSession();
}
