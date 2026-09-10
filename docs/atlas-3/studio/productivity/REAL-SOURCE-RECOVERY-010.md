# ATLAS-STUDIO-REAL-SOURCE-RECOVERY-010

Status: **real native inspection and isolated bridge recovery demonstrated; upstream rate-limit failure remains reproducible evidence**.

## Tested subject

- Preserved automation candidate: `846069013deedd273290ae27cacca36c56c1e7ce` / tree `001ee3fd87a88148a29b517f5db7e88a24b6a028`.
- Earlier implementation checkpoint: `ae43e16f` / tree `007cfa9b`.
- Current Studio source changes are limited to the read-only bridge, error presentation, and the native acceptance runner; application authority and schemas are unchanged.
- Release executable rebuilt from the current source: `apps/studio/src-tauri/target/release/atlas-studio`, SHA-256 `4a1d14e5509c04debabadbcc77f9f35a1ca756963aa8cd864c343d446fdf68cc`.
- WebDriver client: WebdriverIO `9.31.7` (lockfile SHA-256 `b120624026ae953578601faa6cbcb4eac8efb973165dc80d3e25df719510a356`).
- Native driver: `tauri-driver` with `/usr/bin/WebKitWebDriver`; Debian package `webkitgtk-webdriver 2.52.6-0ubuntu0.26.04.1`.
- Bridge source: `apps/studio/bridge/atlas_studio_bridge.py` and `projection_worker.py` at the current worktree revision.

## Real-source diagnosis

The controlled request was `GET http://127.0.0.1:47631/v1/mission-control` with fixtures disabled, repository `B0LK13/project-atlas`, agent `ubuntu-main`, launched from `apps/studio` with the repository Python interpreter `/home/gebruiker/Projects/project-atlas/.venv/bin/python`.

The response was HTTP 503 with reason `PROJECTION_FAILED_UPSTREAM_READS`. One instrumented run through the exact `RequestClient` path recorded 238 bounded reads: authentication and the initial open-PR read succeeded; 235 subsequent `gh api` reads failed with the sanitized category `rate_limit` and GitHub's `API rate limit exceeded` error. The worker emitted the existing stage-coded failure after 5.656 seconds. No Studio parsing, permission, interpreter, or timeout defect was observed. The failure is an upstream GitHub API quota dependency.

The bridge now attaches the allowlisted reference `ATLAS-STUDIO-PROJECTION_FAILED_UPSTREAM_READS`; the UI presents the existing read-failure explanation plus that reference and never reflects upstream diagnostic text.

## Native acceptance

Reproducible command (from `apps/studio`, with `tauri-driver --native-driver /usr/bin/WebKitWebDriver --port 4444` available):

```bash
STUDIO_NATIVE_SOURCE=real STUDIO_NATIVE_MANAGE_BRIDGE=1 npm run native:acceptance
```

Observed with real projection data:

| Check | Result | Evidence |
|---|---|---|
| Mission Control load and source identity | PASS | WebDriver session `f8d87626-7efc-45dd-8210-ebaf812d6295`; repository `B0LK13/project-atlas`; source generated `2026-09-10T10:19:30Z` |
| Attention filter, selection, detail | PASS | `EXTERNAL_IV_GATED`; “Independent verification unavailable” |
| Secondary navigation and return | PASS | Mission Control → Verification → Mission Control |
| Keyboard focus | PASS | WebDriver focus `attention-filter` (`INPUT`) after Tab |
| Isolated bridge disconnect | PASS | `bridge_disconnected_state=true`; unavailable state shown |
| Isolated bridge restart and recovery | PASS | `bridge_recovered_state=true`; controls returned |
| Native webview screenshot | PASS | `apps/studio/artifacts/native/mission-control-real.png` |
| Stale/malformed/incomplete responses | PASS in labeled fixture campaign | Separate fixture evidence retained in `mission-control-filter.png`; not claimed as real-data behavior |

The screenshot is WebDriver webview evidence, not compositor-decoration or AT-SPI evidence. The fixture campaign remains separate and preserved.

## Remaining limits

The real projection depends on GitHub API quota. When quota is exhausted the bridge correctly returns 503, Studio labels the projection unavailable, retains no stale data as current, and exposes the sanitized diagnostic reference. Candidate verification, knowledge, history, mission catalog, and dependency-edge contracts remain outside this A1 projection and are not fabricated here.

CI, independent verification, merge status, and documentation synchronization remain separate statuses. The documentation vault still has 27 raw events and no normalized/routed/validated events or canonical receipt; no synchronization claim is made.

## Quota-efficient continuation

The follow-on cache boundary keys validated projections by repository and agent, coalesces equivalent in-flight reads, and serves a packet for 15 seconds without rewriting its source timestamp. A cold projection remains 238 upstream reads (full source coverage); equivalent concurrent requests and Mission Journey/Task Context calls during the interval share that one collection. An expired entry performs a new cold collection, and failed collections are never cached. This is bounded request coalescing, not a durable truth cache.
