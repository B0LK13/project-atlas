import { execFileSync } from "node:child_process";

const commands = ["tauri-driver", "WebKitWebDriver", "node", "npm"];
for (const command of commands) {
  try {
    const path = execFileSync("sh", ["-lc", `command -v ${command}`], { encoding: "utf8" }).trim();
    console.log(`${command}=${path}`);
  } catch { console.log(`${command}=MISSING`); }
}
try { console.log(`tauri-driver-help=${execFileSync("tauri-driver", ["--help"], { encoding: "utf8" }).split("\n")[0]}`); } catch (error) { console.log(`tauri-driver-help=ERROR ${error.message}`); }
try { console.log(`webkitgtk-webdriver=${execFileSync("dpkg-query", ["-W", "-f=${Version}", "webkitgtk-webdriver"], { encoding: "utf8" }).trim()}`); } catch { console.log("webkitgtk-webdriver=UNKNOWN"); }
console.log(`node-version=${process.version}`);
