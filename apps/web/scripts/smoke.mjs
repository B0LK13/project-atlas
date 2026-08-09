/**
 * AS-WEB-003 smoke — production shell + design-lab presence (no npm install).
 * Exit 0 on success; non-zero on missing artifacts / invariant breaks.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "package.json",
  "README.md",
  "index.html",
  "vite.config.ts",
  "src/main.tsx",
  "src/App.tsx",
  "src/tokens.css",
  "src/styles.css",
  "src/pages/HomePage.tsx",
  "src/pages/production/ProjectsPage.tsx",
  "src/pages/production/OpsHealthPage.tsx",
  "src/pages/production/CommandCenterPage.tsx",
  "src/pages/design-lab/LedgerDeskPage.tsx",
  "src/pages/design-lab/SignalRackPage.tsx",
  "src/pages/design-lab/CartographQuietPage.tsx",
  "src/pages/design-lab/TerminalHonestPage.tsx",
  "src/components/LabNav.tsx",
  "src/components/LabShell.tsx",
  "src/components/ProdNav.tsx",
  "src/components/ProdShell.tsx",
  "src/components/ReadStatusPanel.tsx",
  "src/hooks/useReadStatus.ts",
  "public/sample-read-status.json",
];

const missing = required.filter((rel) => !existsSync(join(root, rel)));
if (missing.length) {
  console.error("AS-WEB-003 smoke FAIL — missing:", missing.join(", "));
  process.exit(1);
}

const stub = JSON.parse(
  readFileSync(join(root, "public/sample-read-status.json"), "utf8"),
);
if (stub.ui_canonical !== false || stub.graph_authority !== false) {
  console.error("AS-WEB-003 smoke FAIL — stub must keep UI/graph non-authority");
  process.exit(1);
}
if (stub.unknown_equals_healthy !== false) {
  console.error("AS-WEB-003 smoke FAIL — unknown_equals_healthy must be false");
  process.exit(1);
}
if (stub.health?.rollup === "healthy" && stub.health?.available === false) {
  console.error("AS-WEB-003 smoke FAIL — unavailable health must not be healthy");
  process.exit(1);
}

const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
if (!pkg.dependencies?.["react-router-dom"]) {
  console.error("AS-WEB-003 smoke FAIL — react-router-dom required for client routes");
  process.exit(1);
}

const tokens = readFileSync(join(root, "src/tokens.css"), "utf8");
for (const theme of [
  "ledger-desk",
  "signal-rack",
  "cartograph-quiet",
  "terminal-honest",
]) {
  if (!tokens.includes(`[data-theme="${theme}"]`)) {
    console.error(`AS-WEB-003 smoke FAIL — missing token theme ${theme}`);
    process.exit(1);
  }
}

const app = readFileSync(join(root, "src/App.tsx"), "utf8");
for (const route of [
  "/projects",
  "/ops",
  "/command-center",
  "/design-lab/ledger-desk",
  "/design-lab/signal-rack",
  "/design-lab/cartograph-quiet",
  "/design-lab/terminal-honest",
]) {
  if (!app.includes(route)) {
    console.error(`AS-WEB-003 smoke FAIL — App missing route ${route}`);
    process.exit(1);
  }
}

const commandCenter = readFileSync(
  join(root, "src/pages/production/CommandCenterPage.tsx"),
  "utf8",
);
for (const mode of ["overview", "projects", "ops", "impact"]) {
  if (!commandCenter.includes(`"${mode}"`) && !commandCenter.includes(`'${mode}'`)) {
    console.error(`AS-WEB-003 smoke FAIL — Command Center missing mode ${mode}`);
    process.exit(1);
  }
}

const main = readFileSync(join(root, "src/main.tsx"), "utf8");
if (!main.includes("HashRouter") && !main.includes("BrowserRouter")) {
  console.error("AS-WEB-003 smoke FAIL — client router missing in main.tsx");
  process.exit(1);
}

const adr = join(root, "..", "..", "docs", "adr", "ADR-010-atlas-web-ux.md");
if (!existsSync(adr)) {
  console.error("AS-WEB-003 smoke FAIL — ADR-010 missing at docs/adr/ADR-010-atlas-web-ux.md");
  process.exit(1);
}

console.log("AS-WEB-003 smoke PASS — production shell + design-lab + ADR-010");
