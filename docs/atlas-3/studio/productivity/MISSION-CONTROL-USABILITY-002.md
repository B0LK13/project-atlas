# Mission Control usability increment

Directive: `ATLAS-STUDIO-MISSION-CONTROL-USABILITY-002`

Candidate lane: `feat/atlas-native-daily-workspace-001`, built on #781 plus the integration baseline. This increment keeps A1 and the Mission Journey/Task Context contracts unchanged and improves only the Studio presentation layer.

The opening now gives compact project context and clearly distinguishes the source limitation (`objective not provided`, no mission catalog) from a selected mission. Attention is a bounded decision queue grouped by the exact source `kind`; every record remains available under “Inspect all … records”. Selecting a group or record opens a keyboard-accessible detail rail with source cause, tier, references, and a supported inspection route. Refresh preserves selection while a record remains present and reports its disappearance when the refreshed projection removes it.

Primary labels translate known source values (`EXTERNAL_IV_GATED`, `HUMAN_GATE`, `BLOCKED_HIGH_VALUE`, `PANEL_STATUS`) while exact values remain in source details. Metrics name their entities (frontier actions, listed agents, actions waiting on CI or independent verification). Connection state, source freshness, and local age are shown separately. The existing read-only boundary remains in the shell; action restrictions stay with the relevant task and inspection surfaces.

Evidence:

- Before: [mission-control-usability-002-before.png](./desktop/evidence/mission-control-usability-002-before.png)
- After: [mission-control-usability-002-after.png](./desktop/evidence/mission-control-usability-002-after.png)
- Native AT-SPI capture: `/tmp/atlas-native-mission-control-002-a11y.json`

Validation:

- `npm run check`: 40 Vitest tests, typecheck, and production build passed.
- Mission Control usability E2E: 1 passed (118-item fixture, grouping, keyboard focus, selection persistence, disappearance).
- Existing controlled accessibility E2E: 4 passed at 600×800, 980×700, 1366×768, and 1920×1080, including axe checks.
- Full browser suite is run before delivery; the real authenticated test remains opt-in.
- Native Tauri Debian bundle rebuilt from this lane; hashes are recorded in the delivery receipt.

Limitations remain source-accurate: A1 supplies no mission catalog or declared mission objective; unknown metrics remain unknown; the bridge does not grant authority or execute actions. Documentation synchronization is attempted only through the governed process; if the remote credit blocker remains, no receipt will be claimed.
