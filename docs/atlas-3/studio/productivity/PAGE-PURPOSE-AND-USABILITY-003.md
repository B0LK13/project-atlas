# Studio page purpose and usability

Directive: `ATLAS-STUDIO-PAGE-PURPOSE-AND-USABILITY-003`

Candidate: `feat/atlas-native-daily-workspace-001`, final commit `f7cd5d28` plus the selection-persistence checkpoint recorded in delivery, built from the #781 Studio shell and existing A1/Mission Journey contracts. This is a presentation-only increment; backend composition, classification, eligibility, recovery, and authority semantics are unchanged.

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
- Final executable SHA-256: `3db8c4cd8601e00fd9b5ef7a850603d70969e216bf82c4cb9ad74861693eb8e2`.
- Final Debian SHA-256: `19f9a49c959812aec40f4bbb1cf507484190be0649cb9a834bf20f4640354c61`.

Remaining contract limits are explicit: A1 supplies no mission catalog, objective, candidate dependency graph, complete candidate table, or connected knowledge/history feed. Aggregate fields remain labeled as aggregates, unknown data is not converted to zero, and fixture mode remains separate from live source mode.

**ATLAS-DOC-RECEIPT:** `NOT_ISSUED`. Governed synchronization previously returned HTTP 400 because the configured remote lacked Anthropic API credits. No documentation synchronization success is claimed.
