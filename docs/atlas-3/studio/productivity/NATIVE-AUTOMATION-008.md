# Native Automation 008

## Capability matrix

| Capability | Result | Evidence |
|---|---|---|
| Tauri CLI | available | project `@tauri-apps/cli` 2.8.4; `npm run tauri:build` |
| Rust/Cargo | available | rustc/cargo 1.98.1 |
| Node/npm | available | Node 22.23.2, npm 10.9.8 |
| WebKitGTK | available | `libwebkit2gtk-4.1-0` 2.52.6 |
| WebKitWebDriver | available | `/usr/bin/WebKitWebDriver`, `webkitgtk-webdriver` 2.52.6 |
| tauri-driver | available | `/home/gebruiker/.cargo/bin/tauri-driver`; explicit `--native-driver` supported |
| WebdriverIO | pinned | `webdriverio` 9.31.7 (test-only dev dependency) |
| Wayland screenshot binaries | missing | `grim`, `gnome-screenshot`, `spectacle`, `wf-recorder` absent |
| Browser automation | available | Playwright; browser evidence only |
| AT-SPI controls | unverified | bus reachable; no Atlas accessible tree exposed in this session |

## Reproducible native route

Start the isolated read-only bridge on `127.0.0.1:47631`, then start the driver:

```bash
cd apps/studio
tauri-driver --native-driver /usr/bin/WebKitWebDriver --port 4444
```

In a second terminal, run `STUDIO_NATIVE_SOURCE=fixture npm run native:acceptance` for deterministic labeled fixture evidence. The command launches the identified binary through `tauri-driver`, locates Mission Control, focuses the loaded-record filter, selects an attention group, navigates to Verification, returns to Mission Control, and saves a WebDriver PNG under `apps/studio/artifacts/native/`.

`npm run native:prereqs` checks the installed route; `npm run native:inspect` reports evidence hashes. Stop only the driver and bridge processes created for the run. WebDriver screenshots are native webview captures, not compositor or window-decoration captures.

The fixture runner owns its temporary HTTP server and closes it in `finally`, including when WebDriver session creation or an assertion fails. For real data, leave the supported read-only bridge running separately and set `STUDIO_NATIVE_SOURCE=real`; a 2026-09-10 attempt returned `503 PROJECTION_FAILED_UPSTREAM_READS`, so no real-data journey is claimed.

## Evidence

- Current implementation candidate preserved: `28ac8677`, tree `eb9aeb9037f0de0843ca143b98a55d35d9f807ba6`
- Diagnosis documentation head: `adc30219` and later documentation commits
- Native executable SHA-256: `0438b41843ea211e10b920c1a03908be6c532b1de9354cf8fcf6ae03cdb8d82e`
- Fixture native webview capture: `apps/studio/artifacts/native/mission-control-filter.png`, SHA-256 `b7d49c34619c2df0d7f5eb57888cb01278454634ada985c20fd9b6d44f00f86d`
- Real bridge smoke: one WebDriver session loaded Mission Control, located the filter, activated it, and returned HTTP 200 from the raw screenshot endpoint; real upstream timing can leave the projection unavailable and is reported separately from fixture results.
- Complete fixture campaign: navigation/return, keyboard focus, filter, changed detail, selected-record disappearance, stale, malformed, and recovered states all passed through observable native WebDriver UI conditions.
