# Studio page purpose and usability

Directive: `ATLAS-STUDIO-PAGE-PURPOSE-AND-USABILITY-003`

Candidate: `feat/atlas-native-daily-workspace-001`, final commit `3be626b2`, built from the #781 Studio shell and existing A1/Mission Journey contracts. This is a presentation-only increment; backend composition, classification, eligibility, recovery, and authority semantics are unchanged.

The shared secondary-route structure now puts a route-specific purpose question and source-shaped detail first. Global attention is represented by one compact count/link to Mission Control rather than a repeated full queue. Mission Control retains the bounded grouped queue and selected record detail. View names are deliberate (`Observed agent directory`, `Frontier action summary`, `Repository stack records`, `CI and independent verification`, `Telemetry snapshot`) while exact source values remain available in details.

Before/after evidence:

- [page-purpose-003-before.png](../desktop/evidence/page-purpose-003-before.png)
- [page-purpose-003-after.png](../desktop/evidence/page-purpose-003-after.png)
- Native Mission Control AT-SPI: `/tmp/atlas-native-page-purpose-003-mission.json`
- Native Agents AT-SPI: `/tmp/atlas-native-page-purpose-003-agents.json`
- Native Work Graph AT-SPI: `/tmp/atlas-native-page-purpose-003-workgraph.json`

Validation:

- `npm run check`: 43 Vitest tests, typecheck, and production build passed.
- Full Playwright suite: 20 passed, 1 skipped (authenticated real-data test remains opt-in).
- Mission Control usability fixture: 118 attention records, grouped selection, keyboard focus, refresh persistence, browser-back context, reload persistence, and disappearance handling; passed.
- Controlled accessibility viewports: 600×800, 980×700, 1366×768, 1920×1080; axe checks passed.
- Native Tauri Debian bundle rebuilt and opened on Linux; AT-SPI confirmed Mission Control, Agents, and Work Graph purpose content.
- Final executable SHA-256: `025a932ef9a03e6ddc739836bf511b28d67fb24b3efc8bfa4bd1d9507df96c0b`.
- Final Debian SHA-256: `3ff6d51b58929e9596418e99796063adb3b0af50f59c38cec87fd8504f32ee54`.

Remaining contract limits are explicit: A1 supplies no mission catalog, objective, candidate dependency graph, complete candidate table, or connected knowledge/history feed. Aggregate fields remain labeled as aggregates, unknown data is not converted to zero, and fixture mode remains separate from live source mode.

**ATLAS-DOC-RECEIPT:** `NOT_ISSUED`. Governed synchronization previously returned HTTP 400 because the configured remote lacked Anthropic API credits. No documentation synchronization success is claimed.
