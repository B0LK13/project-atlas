# Atlas 2.0 — Open questions (prep)

Status: **PREP ONLY**. Production answers blocked on 1.0 freeze.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Identity and federation

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-001 | Federation identity model vs AS-ID-001 locks | (a) operator manifest join; (b) discovery with quarantine | 1.0 freeze + FED entry gate | AS-2.0-FED-001 |
| OQ-002 | Cross-vault project ID collision resolution | fail-closed quarantine vs namespaced IDs | AS-XPROJ-001 maturity | AS-2.0-FED-001 |
| OQ-003 | Global entity registry ownership | Core vs graph vs federation package | AS-XPROJ-001 | AS-2.0-FED-001 |

## Provider and quarantine

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-004 | Provider adapter quarantine boundary | in-process vs subprocess sandbox | NFR-006 adapter design | AS-2.0-PROV-001 |
| OQ-005 | Model-assisted classification precedence | deterministic-first always vs opt-in override | FR-004 policy | AS-2.0-PROV-001 |
| OQ-006 | Provider receipt shape | extend agent-event vs new contract | AS-CTRL-001 | AS-2.0-PROV-001 |

## Web and UX

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-007 | Command Center advanced modes vs WEB 1.0 acceptance | ship modes incrementally vs batch | WEB APPLICATION ACCEPTED | AS-2.0-UX-001 |
| OQ-008 | Live vault adapter vs sample stub default | env-configured vault path vs fixture-only | AS-WEB-ACCEPT-001 | AS-2.0-UX-001 |
| OQ-009 | Impact lens data source | AS-J-005 projection only vs multi-source | AS-J-005 maturity | AS-2.0-UX-001 |

## Sync and migration

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-010 | Migration tooling ownership (INT-012 vs 2.0-COMPAT) | INT owns tooling; 2.0 consumes snapshot | INT-012 entry | AS-2.0-COMPAT-001 |
| OQ-011 | Estate sync v2 tombstone semantics | hard delete vs soft tombstone vs retention archive | AS-INT-010 policy | AS-2.0-SYNC-001 |
| OQ-012 | Partial sync failure recovery | promote rollback vs forward-fix receipt | AS-CORE2-009 | AS-2.0-SYNC-001 |

## Compatibility and release

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-013 | Snapshot pin format | YAML manifest vs JSON contract bundle | 1.0 release cert | AS-2.0-COMPAT-001 |
| OQ-014 | 2.0 major version boundary | semantic vs calendar vs capability flag | governor decision | all stubs |
| OQ-015 | Threat model control promotion | which T-2.0-xxx mitigations ship in 2.0 MVP | threat review | THREAT-MODEL.md |

## Deepen-f blockers (unanswered)

| # | Question | Options (sketch) | Blocker | Related stub |
|---|---|---|---|---|
| OQ-016 | Who issues and verifies federation join authorization, and what is its canonical signed form? | release governor trust root vs operator trust bundle | 1.0 identity/release trust decision | AS-2.0-FED-001 |
| OQ-017 | What evidence can set WEB APPLICATION ACCEPTED without allowing a route-render or sample-data false stamp? | independent acceptance receipt vs governor-signed evidence bundle | WEB acceptance governance | AS-2.0-UX-001 |
| OQ-018 | What authorizes a queued sync plan, and how do cancellation, expiry, and replay retain operation identity? | per-plan authorization vs scoped session authorization | sync/recovery policy | AS-2.0-SYNC-001 |
| OQ-019 | What machine-readable evidence class distinguishes fixture rehearsal, fixture-only waiver, and authentic estate pilot pass? | typed receipt vs separately governed manifests | ESTATE PILOT gate owner | AS-2.0-SYNC-001 / COMPAT |

These questions are newly captured blockers. No option is selected or resolved.

All production answers require `ATLAS_1_0_RELEASE_CERTIFIED` first.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial four open questions |
| 2026-08-09 | Structured OQ table with blockers and stub links |
| 2026-08-09 | deepen-f: added unresolved OQ-016…019 for trust, acceptance, sync authorization, and evidence class |
