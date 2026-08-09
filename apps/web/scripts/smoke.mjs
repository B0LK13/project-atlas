/**
 * AS-WEB-001 smoke — file/shape presence without requiring npm install.
 * Exit 0 on success; non-zero on missing foundation artifacts.
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
  "public/sample-read-status.json",
];

const missing = required.filter((rel) => !existsSync(join(root, rel)));
if (missing.length) {
  console.error("AS-WEB-001 smoke FAIL — missing:", missing.join(", "));
  process.exit(1);
}

const stub = JSON.parse(
  readFileSync(join(root, "public/sample-read-status.json"), "utf8"),
);
if (stub.ui_canonical !== false || stub.graph_authority !== false) {
  console.error("AS-WEB-001 smoke FAIL — stub must keep UI/graph non-authority");
  process.exit(1);
}
if (stub.unknown_equals_healthy !== false) {
  console.error("AS-WEB-001 smoke FAIL — unknown_equals_healthy must be false");
  process.exit(1);
}
if (stub.health?.rollup === "healthy" && stub.health?.available === false) {
  console.error("AS-WEB-001 smoke FAIL — unavailable health must not be healthy");
  process.exit(1);
}

console.log("AS-WEB-001 smoke PASS — foundation shell present");
