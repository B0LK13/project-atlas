#!/usr/bin/env node
/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 honesty gates.
 * Source-inspect the web consumer only. No vault writes. No LIVE_API calls.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(root, "..", "..");

function fail(message) {
  console.error(`AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 FAIL — ${message}`);
  process.exit(1);
}

function read(rel) {
  const path = join(root, rel);
  if (!existsSync(path)) {
    fail(`missing ${rel}`);
  }
  return readFileSync(path, "utf8");
}

const required = [
  "src/hooks/useLiveSourceHealth.ts",
  "src/pages/production/SourceHealthPage.tsx",
  "src/App.tsx",
  "src/components/ProdNav.tsx",
  "src/pages/HomePage.tsx",
  "scripts/test-source-health-web.mjs",
];
for (const rel of required) {
  if (!existsSync(join(root, rel))) {
    fail(`missing ${rel}`);
  }
}

const hook = read("src/hooks/useLiveSourceHealth.ts");
const page = read("src/pages/production/SourceHealthPage.tsx");
const app = read("src/App.tsx");
const nav = read("src/components/ProdNav.tsx");
const home = read("src/pages/HomePage.tsx");
const pkg = JSON.parse(read("package.json"));
const evidence = join(repoRoot, "docs", "AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001.md");

if (!pkg.scripts?.["test:source-health"]) {
  fail("package.json missing test:source-health");
}
if (!existsSync(evidence)) {
  fail("missing docs/AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001.md");
}

for (const [label, body, needles] of [
  ["hook", hook, [
    "liveApiFetch",
    "/v1/source-health?project=",
    "if (!projectId)",
    "health_state",
    "liveApiDemoOnly",
    "No implicit portfolio-all",
    "No secret echo",
  ]],
  ["page", page, [
    "useLiveSourceHealth",
    "?project=",
    "UNKNOWN",
    "UNREADABLE",
    "SOURCE HEALTH != AUTHORITY",
    "UI != CANONICAL TRUTH",
    "No secret echo",
    "no implicit portfolio-all",
    "reason_code",
    "human_explanation",
    "opaque",
  ]],
  ["App", app, ["/source-health", "SourceHealthPage"]],
  ["ProdNav", nav, ["/source-health", "Source Health"]],
  ["HomePage", home, ["/source-health", "Source health"]],
]) {
  for (const needle of needles) {
    if (!body.includes(needle)) {
      fail(`${label} missing ${needle}`);
    }
  }
}

if (!nav.includes('"/source-health"') && !nav.includes("'/source-health'")) {
  fail("ProdNav must treat /source-health as project-aware");
}
const awareBlock = nav.match(/PROJECT_AWARE_PATHS[\s\S]*?\]\s*\)/);
if (!awareBlock || !awareBlock[0].includes("/source-health")) {
  fail("ProdNav PROJECT_AWARE_PATHS must include /source-health");
}

if (hook.includes("portfolio-all") && !hook.includes("No implicit portfolio-all")) {
  fail("hook must not implement portfolio-all");
}
if (/liveApiFetch\(`\/v1\/source-health`\)/.test(hook)) {
  fail("hook must not call /v1/source-health without project");
}
if (!hook.includes("if (!projectId)")) {
  fail("hook must refuse to fetch without an explicit project");
}

const staleCompare = /health[_A-Za-z]*\s*===\s*["']STALE["']/;
if (staleCompare.test(hook) || staleCompare.test(page)) {
  fail("health_state must stay opaque; do not special-case STALE");
}

for (const forbidden of [
  "matched_content",
  "secret_value",
  "password",
  "Bearer ",
  "ATLAS_API_READ_TOKEN",
]) {
  if (hook.includes(forbidden) || page.includes(forbidden)) {
    fail(`secret echo risk: ${forbidden}`);
  }
}

if (!page.includes('healthState === "UNKNOWN"') || !page.includes('healthState === "UNREADABLE"')) {
  fail("page must special-case UNKNOWN and UNREADABLE honestly");
}
if (!page.includes("typeof value === \"string\"") && !page.includes("typeof value === 'string'")) {
  fail("page must treat health_state as an opaque string");
}

console.log("AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 test:source-health PASS");
