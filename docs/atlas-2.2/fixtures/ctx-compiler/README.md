# Context Compiler fixtures (PREP)

Status: **PREP ONLY** — synthetic rehearsal payloads.  
**Not** runnable harness · **Not** CI-gated · **Not** PILOT evidence · **Not** production schemas.

Package: **AS-2.2-CTX-COMPILER-001**.

## Inventory

| Scenario | Files | Expectation |
|---|---|---|
| FX-2.2-CTX-001 | `task-developer.request.json` + `expected-package-developer.json` | Pipeline stages present; items carry authority/freshness/reason |
| FX-2.2-CTX-002 | `negative-estate-invent.request.json` + `expected-estate-invent-fail.json` | Reject invent-estate force path |
| FX-2.2-CTX-003 | `negative-budget-overflow.request.json` + `expected-budget-fail.json` | Hard overflow → fail closed |
| FX-2.2-CTX-004 | `conflict-filter.request.json` + `expected-conflict-package.json` | Unresolved conflict retained as sidecar, no silent winner |

## Rules

- Synthetic relative refs only (`fixture/...`)
- No secrets, credentials, host paths, or raw provider payloads
- `fixture_safe: true` and `estate_facts_invented: false` always
- Future runners must treat these as **docs-owned drafts** until unlock

## Evidence class

| Class | Value |
|---|---|
| Fixture rehearsal | YES (docs) |
| Production coverage | NO |
| Authentic PILOT | NO |
| Release credit | NO |
