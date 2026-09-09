# Atlas Studio desktop recovery candidate

This is a read-only desktop review candidate. The live browser experience is validated; native Linux acceptance and canonical documentation synchronization remain incomplete. See
[latest recovery](RECOVERY-005.md) for exact upstream observations and acceptance gaps.

## Linux development

Prerequisites: Node 22.12+ or supported Node 24, npm, Python 3.12 with the repository
development environment installed at the repository root .venv, Rust stable, and
Ubuntu packages build-essential, pkg-config, libgtk-3-dev, libwebkit2gtk-4.1-dev,
libayatana-appindicator3-dev, librsvg2-dev, patchelf, libssl-dev.
The existing Atlas GitHub reader also needs the GitHub CLI authenticated through
its supported login flow. Do not supply credentials through Studio.

From apps/studio, run npm ci once, then npm run desktop:dev.
For browser development use npm run dev:live.
The read bridge listens on 127.0.0.1:47631; Vite uses port 1420.
Production builds use npm run tauri:build -- --bundles deb.
Packaging is a spike; installing the package does not install or start the read bridge.

For browser tests run npx playwright install chromium, then npm run test:e2e
as an ordinary user in an environment supporting Chromium sandboxing.
PLAYWRIGHT_CHROMIUM_EXECUTABLE optionally selects an approved installed browser.
No fixed system Chrome path or sandbox-disabling option is configured.

## Source coverage

| Screen | Real fields from A1 | Preview / unavailable detail |
|---|---|---|
| Mission Control | repository, mission_status, freshness, attention, every views summary/status/notes | No invented mission objective |
| Projects | health, residuals | Portfolio breadth unavailable |
| Agents | agents_lanes, ownership | Model, elapsed work and individual agent cards preview only |
| Work Graph | frontier, ownership | Node/edge topology preview only |
| Repository | stacks | Working tree, diff and exact Git objects preview only |
| Verification | ci_iv, human_gates, evidence, postmerge_seal | Stage pipeline preview only |
| Knowledge | none | Knowledge cards preview only |
| Chronicle | telemetry summary | Narrative event history preview only |
| Environment | local presentation settings and selected source | No runtime administration |

The adapter uses ATLAS_STUDIO_MISSION_CONTROL_V1. Field names and values are
rendered without deriving authorization. Null summaries are unavailable; empty
attention means no items were supplied, not healthy. Loading clears old content,
failed refresh remains unavailable, and stale/offline packets keep their source
labels. No failed request substitutes fixtures. Provenance timestamps are labeled
source supplied. No local time is passed off as an Atlas observation.

The Design Lab remains isolated design evidence. Rich preview pages are selected
through Environment → Design fixture and never labeled live.

Current acceptance: 36 frontend tests, 16 browser tests including real A1 input, nested-contract and clock-rollback regressions, automated accessibility and manual keyboard review. See RECOVERY-005 and its validation ledger for exact Python results and remaining blockers. Use the recovered checkout’s own `.venv`, including for subprocess tests; a shared venv can silently import another worktree.
