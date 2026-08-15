/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — focused web contract gates.
 * Source-level (matches apps/web smoke / node-assert style). No vault writes.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const hookPath = join(root, "src/hooks/useLiveSourceHealth.ts");
const pagePath = join(root, "src/pages/production/SourceHealthPage.tsx");
const appPath = join(root, "src/App.tsx");
const navPath = join(root, "src/components/ProdNav.tsx");
assert.ok(existsSync(hookPath), "useLiveSourceHealth.ts must exist");
assert.ok(existsSync(pagePath), "SourceHealthPage.tsx must exist");

const hook = readFileSync(hookPath, "utf8");
const page = readFileSync(pagePath, "utf8");
const app = readFileSync(appPath, "utf8");
const nav = readFileSync(navPath, "utf8");

assert.match(hook, /\/v1\/source-health\?project=/);
assert.match(hook, /encodeURIComponent\(projectId\)/);
assert.match(hook, /liveApiDemoOnly/);
assert.match(hook, /liveApiFetch/);
assert.match(hook, /demo_stub/);
assert.match(hook, /live_api/);
assert.match(hook, /if \(!projectId\)/);
assert.doesNotMatch(hook, /Authorization:\s*`?Bearer\s+[A-Za-z0-9_\-]{16,}/);
assert.doesNotMatch(hook, /sample-source-health/);

assert.match(page, /SOURCE HEALTH != AUTHORITY/);
assert.match(page, /ui_canonical=false/);
assert.match(page, /score_theatre=false/);
assert.match(page, /write_controls=false/);
assert.match(page, /reason_code/);
assert.match(page, /human_explanation/);
assert.match(page, /DEGRADED \/ UNAVAILABLE/);
assert.match(page, /DEMO STUB isolated/);
assert.match(page, /explicit project required/);
assert.match(page, /useLiveSourceHealth/);
assert.doesNotMatch(page, /type=["']submit["']/);
assert.doesNotMatch(page, /method=["']POST["']/);
assert.doesNotMatch(page, /accept-review|promote|reject-source/i);
assert.doesNotMatch(page, /confidence[_ ]?score/i);
assert.doesNotMatch(page, /health_score|percent_complete|completion_pct/i);

assert.match(app, /path="\/source-health"/);
assert.match(nav, /to: "\/source-health"/);
assert.match(nav, /"\/source-health"/);

console.log("AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 contract gates: PASS");
