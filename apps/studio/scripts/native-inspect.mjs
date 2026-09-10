import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";

const dir = path.resolve(process.env.STUDIO_NATIVE_EVIDENCE_DIR ?? "artifacts/native");
for (const name of fs.existsSync(dir) ? fs.readdirSync(dir).sort() : []) {
  const file = path.join(dir, name);
  if (fs.statSync(file).isFile()) console.log(`${file} sha256=${crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex")}`);
}
