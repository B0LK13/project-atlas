import { writeFileSync } from "node:fs";
import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import input from './controlled-projection.json' with { type: 'json' };

const endpoint = 'http://127.0.0.1:47631/v1/mission-control';
function controlled(count = 7) {
  const packet = structuredClone(input);
  packet.generated_at_utc = new Date().toISOString();
  packet.freshness.generated_at_utc = packet.generated_at_utc;
  packet.freshness.state = 'LIVE';
  packet.freshness.age_seconds = 0;
  packet.views.health.summary = { test_input_count: count };
  return packet;
}

test('controlled A1 input changes render, failed refresh clears it, fixtures stay isolated', async ({ page }, info) => {
  let count = 7, failed = false;
  await page.route(endpoint, route => route.fulfill({status: failed ? 503 : 200,
    contentType: 'application/json', body: JSON.stringify(failed ? {} : controlled(count))}));
  await page.goto('/#/mission-control');
  await expect(page.getByRole('status')).toContainText('READ-ONLY PROJECTION');
  await expect(page.locator('.projection-fields').filter({hasText: 'test input count'})).toContainText('7');
  await page.screenshot({path:info.outputPath('controlled-before.png'),fullPage:false});
  count = 11;
  await page.getByRole('button', {name:'Refresh read-only projection'}).click();
  await expect(page.locator('.projection-fields').filter({hasText: 'test input count'})).toContainText('11');
  await page.screenshot({path:info.outputPath('controlled-after.png'),fullPage:false});
  failed = true;
  await page.getByRole('button', {name:'Refresh read-only projection'}).click();
  await expect(page.getByRole('heading', {name:'Projection unavailable'})).toBeVisible();
  await expect(page.locator('main')).not.toContainText('test input count');
  await expect(page.getByRole('status')).not.toContainText('FIXTURE');
  await page.screenshot({path:info.outputPath('failed-refresh.png'),fullPage:false});
});

test('untrusted nested projection is rejected and no HTML executes', async ({page}) => {
  const packet = controlled();
  packet.studio_snapshot.honesty.studio_ui_ne_authority = false;
  await page.route(endpoint, route => route.fulfill({contentType:'application/json',body:JSON.stringify(packet)}));
  await page.goto('/#/mission-control');
  await expect(page.getByRole('heading', {name:'Projection unavailable'})).toBeVisible();
  await expect(page.locator('main')).not.toContainText('test input count');
});

for (const [width,height] of [[600,800],[980,700],[1366,768],[1920,1080]]) {
  test(`controlled projection controls and accessibility ${width}x${height}`, async ({page}, info) => {
    await page.setViewportSize({width,height});
    await page.route(endpoint, route => route.fulfill({contentType:'application/json',body:JSON.stringify(controlled())}));
    await page.goto('/#/mission-control');
    await expect(page.locator('main')).toContainText('test input count');
    await expect(page.getByRole('button',{name:'Refresh read-only projection'})).toBeInViewport();
    if (width >= 980) await expect(page.getByRole('heading', {name:'Mission Control'})).toBeInViewport();
    const overflow = await page.evaluate(() => Array.from(document.querySelectorAll('*'))
      .filter(el => el.getBoundingClientRect().right > innerWidth + 1)
      .map(el => ({tag:el.tagName, className:el.className, right:el.getBoundingClientRect().right})).slice(0,12));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), JSON.stringify(overflow)).toBe(true);
    const results = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
    await page.screenshot({path:info.outputPath('controlled-viewport.png'),fullPage:false});
    await page.getByRole('button',{name:/Navigate Studio screens/}).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    const dialogAudit = await new AxeBuilder({page}).include('[role="dialog"]').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(dialogAudit.violations).toEqual([]);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button',{name:/Navigate Studio screens/})).toBeFocused();
  });
}

test('actual authenticated A1 HTTP projection renders without interception', async ({page}, info) => {
  test.skip(process.env.STUDIO_REAL_ACCEPTANCE !== '1', 'Explicit authenticated real-data acceptance');
  await page.setViewportSize({width:1366,height:768});
  let responsePacket: unknown;
  page.on('response', async response => {
    if (response.url() === endpoint && response.ok()) responsePacket = await response.json();
  });
  await page.goto('/#/mission-control');
  await expect(page.getByRole('status')).toContainText('CURRENT READ-ONLY PROJECTION',{timeout:26000});
  await expect(page.locator('main')).toContainText('B0LK13/project-atlas');
  await expect(page.locator('main')).not.toContainText('TEST-INPUT');
  await expect(page.getByRole('status')).not.toContainText('FIXTURE');
  await expect.poll(() => responsePacket).toBeDefined();
  const received = responsePacket as {views: Record<string, {summary: Record<string, unknown>}>};
  await expect(page.locator('[aria-label="Agent activity"] .signal-reading strong')).toHaveText(String(received.views.agents_lanes.summary.active_count));
  const counts = page.locator('[aria-label="Verification posture"] .signal-pair strong');
  await expect(counts.nth(0)).toHaveText(String(received.views.ci_iv.summary.waiting_ci));
  await expect(counts.nth(1)).toHaveText(String(received.views.ci_iv.summary.waiting_iv));
  writeFileSync(info.outputPath('actual-a1.json'), JSON.stringify(responsePacket, null, 2));
  await page.screenshot({path:info.outputPath('real-a1-1366x768.png'),fullPage:false});
  await info.attach('actual-a1-packet',{body:JSON.stringify(responsePacket),contentType:'application/json'});
  const audit = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
});

test('explicit fixture selection cancels a pending real request and cannot leak back', async ({page}) => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => {release=resolve;});
  await page.route(endpoint, async route => {
    await pending;
    await route.fulfill({contentType:'application/json',body:JSON.stringify(controlled(999))}).catch(() => {});
  });
  await page.goto('/#/settings');
  await page.getByRole('button',{name:'Design fixture',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('FIXTURE');
  release();
  await page.goto('/#/mission-control');
  await expect(page.getByRole('status')).toContainText('FIXTURE');
  await expect(page.locator('main')).not.toContainText('test input count');
});

test('narrow keyboard navigation never tabs into the closed offscreen rail', async ({page}) => {
  await page.setViewportSize({width:600,height:800});
  await page.route(endpoint, route => route.fulfill({status:503,body:'{}'}));
  await page.goto('/#/mission-control');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link',{name:'Skip to project view'})).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'Open navigation',exact:true})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button',{name:'Close navigation',exact:true})).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button',{name:'Environment',exact:true})).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'Close navigation',exact:true})).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button',{name:'Open navigation',exact:true})).toBeFocused();
});

test('preview graph is explicitly isolated and fitted within its viewport', async ({page}, info) => {
  await page.setViewportSize({width:980,height:700});
  await page.route(endpoint, route => route.fulfill({status:503,body:'{}'}));
  await page.goto('/#/settings');
  await page.getByRole('button',{name:'Design fixture',exact:true}).click();
  await page.evaluate(() => {location.hash='/work-graph';});
  await expect(page.getByRole('status')).toContainText('FIXTURE');
  await expect(page.locator('.graph-node').first()).toBeVisible();
  await page.getByRole('button',{name:'Reset graph view'}).click();
  await expect.poll(() => page.evaluate(() => {
    const frame = document.querySelector('.graph-viewport')!.getBoundingClientRect();
    return Array.from(document.querySelectorAll('.graph-node')).every(node => {
      const box = node.getBoundingClientRect();
      return box.left >= frame.left && box.right <= frame.right && box.top >= frame.top && box.bottom <= frame.bottom;
    });
  })).toBe(true);
  await page.getByRole('button',{name:'Zoom in',exact:true}).click();
  await page.getByRole('button',{name:'Reset graph view'}).click();
  await page.screenshot({path:info.outputPath('preview-graph-980x700.png'),fullPage:false});
});

test('an open window ages out without refreshing source evidence', async ({page}, info) => {
  const packet = controlled();
  packet.freshness.max_age_seconds = 1;
  await page.clock.install({time:new Date(packet.freshness.generated_at_utc)});
  await page.route(endpoint, route => route.fulfill({contentType:'application/json',body:JSON.stringify(packet)}));
  await page.goto('/#/mission-control');
  await expect(page.getByRole('status')).toContainText('CURRENT READ-ONLY PROJECTION');
  await page.clock.fastForward(2000);
  await expect(page.getByRole('status')).toContainText('STALE READ-ONLY PROJECTION');
  await expect(page.locator('.screen-header')).toContainText('STALE');
  await page.screenshot({path:info.outputPath('controlled-stale.png'),fullPage:false});
  await page.getByText('Projection provenance',{exact:true}).click();
  await expect(page.locator('main')).toContainText(packet.generated_at_utc);
});
