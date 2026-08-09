# Atlas 2.0 — Open questions (prep) · dispositions

Status: **PREP ONLY**. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.
Production binding still requires `ATLAS_1_0_RELEASE_CERTIFIED` + owner/governor where noted.

Disposition legend:

| Disposition | Meaning |
|---|---|
| `ANSWERED-DRAFT` | Agent-eligible default selected from existing 1.0 principles; **not** production freeze |
| `DEFERRED-WITH-WAIVER` | Explicitly deferred until named owner/1.0 gate; not ignored |

## Identity and federation

| # | Question | Disposition | Draft answer / waiver |
|---|---|---|---|
| OQ-001 | Federation identity vs AS-ID-001 | `ANSWERED-DRAFT` | **(a) operator manifest join only** — no discovery-as-consent; aligns fail-closed / no invent |
| OQ-002 | Cross-vault project ID collision | `ANSWERED-DRAFT` | **Fail-closed quarantine** — no namespaced silent merge; AS-ID-001 / XPROJ posture |
| OQ-003 | Global entity registry ownership | `DEFERRED-WITH-WAIVER` | Deferred to owner after XPROJ maturity + READY; interim: Core-owned derived registry, graph consume-only |
| OQ-016 | Federation join issuer / signed form | `DEFERRED-WITH-WAIVER` | Deferred to release governor trust-root decision after 1.0 RELEASE CERTIFIED |

## Provider and quarantine

| # | Question | Disposition | Draft answer / waiver |
|---|---|---|---|
| OQ-004 | Adapter quarantine boundary | `ANSWERED-DRAFT` | **Subprocess sandbox preferred**; in-process allowed only with mandatory quarantine + deny write tools (NFR-006) |
| OQ-005 | Model-assisted classification precedence | `ANSWERED-DRAFT` | **Deterministic-first always** — model never overrides FR-004 without explicit quarantine path |
| OQ-006 | Provider receipt shape | `ANSWERED-DRAFT` | **Extend agent-event / provenance receipts** where possible; new contract only if gaps proven at freeze |

## Web and UX

| # | Question | Disposition | Draft answer / waiver |
|---|---|---|---|
| OQ-007 | Advanced CC modes vs WEB acceptance | `DEFERRED-WITH-WAIVER` | Deferred until `WEB APPLICATION ACCEPTED = YES` (governor #10) |
| OQ-008 | Live vault vs sample stub default | `ANSWERED-DRAFT` | **Fixture/sample default**; live path only via explicit config after WEB ACCEPTED |
| OQ-009 | Impact lens data source | `ANSWERED-DRAFT` | **AS-J-005 derived projection only** as default; multi-source requires freeze review |
| OQ-017 | WEB ACCEPTED evidence without false stamp | `ANSWERED-DRAFT` | **Governor-signed evidence bundle** bound to tip SHA/TREE (AS-WEB-ACCEPT-005); route-render alone insufficient |

## Sync and migration

| # | Question | Disposition | Draft answer / waiver |
|---|---|---|---|
| OQ-010 | Migration tooling ownership | `ANSWERED-DRAFT` | **INT owns tooling**; AS-2.0-COMPAT consumes certified snapshot |
| OQ-011 | Estate sync tombstone semantics | `DEFERRED-WITH-WAIVER` | Deferred until PILOT/INT-010 estate policy owner decision |
| OQ-012 | Partial sync failure recovery | `ANSWERED-DRAFT` | **Forward-fix recovery receipt** (CORE2-009 posture); no silent rollback invent |
| OQ-018 | Sync queue authorization / replay | `DEFERRED-WITH-WAIVER` | Deferred until PILOT + production SYNC cert path; scaffolds remain unauthorized dry-run |

## Compatibility, release, evidence

| # | Question | Disposition | Draft answer / waiver |
|---|---|---|---|
| OQ-013 | Snapshot pin format | `DEFERRED-WITH-WAIVER` | Deferred until 1.0 RELEASE CERTIFIED publishes pin |
| OQ-014 | 2.0 major version boundary | `DEFERRED-WITH-WAIVER` | Deferred to governor at READY flip |
| OQ-015 | Threat control promotion to MVP | `DEFERRED-WITH-WAIVER` | Deferred to threat/governor review at freeze; register T-2.0-001…028 is prep-complete |
| OQ-019 | Fixture vs waiver vs estate evidence class | `ANSWERED-DRAFT` | **Typed classes**: `fixture_rehearsal` \| `fixture_only_waiver` \| `estate_pilot_pass` — mutually exclusive; waiver ≠ PILOT PASS |

## Counts

| Metric | Value |
|---|---|
| Total OQ | 19 (001–019) |
| `ANSWERED-DRAFT` | 11 |
| `DEFERRED-WITH-WAIVER` | 8 |
| Silently ignored | **0** |

## Explicit

Dispositions do **not** flip `ATLAS_2_0_IMPLEMENTATION_READY`, RELEASE, WEB ACCEPTED, or PILOT.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial / structured OQ tables |
| 2026-08-09 | deepen-f: OQ-016…019 |
| 2026-08-09 | deepen-j: full disposition table ANSWERED-DRAFT / DEFERRED-WITH-WAIVER |
