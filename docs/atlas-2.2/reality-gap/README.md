# Atlas 2.2 — Reality Gap (PREP)

Status: **PREP ONLY** — architecture + contracts + fixtures.  
No production schema freeze. No runnable 2.2 Reality Gap engine.

Package: [`AS-2.2-REALITY-GAP-PREP-001`](AS-2.2-REALITY-GAP-PREP-001.md)

## Documents

| Doc | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, data flow, truth boundaries |
| [CONTRACT.md](CONTRACT.md) | Stub schema index + FR stubs |
| [INVARIANTS.md](INVARIANTS.md) | unknown≠healthy / UI≠canonical / no PILOT invent |
| [FIXTURE-PLAN.md](FIXTURE-PLAN.md) | Reserved fixture families / scenarios |

Contracts: [`contracts/`](contracts/)  
Fixtures: [`fixtures/`](fixtures/)  
ADR: [`../../adr/ADR-028-reality-gap-prep.md`](../../adr/ADR-028-reality-gap-prep.md)

## Relation to 2.0 / 2.1

```text
AS-2.0-REALITY-GAP-001 (fixture inventory)
AS-2.0-REALITY-GAP-UI-001 (read-only UI catalog; UI≠canonical)
        |
        |  PREP (this tree) — docs / stubs / fixtures only
        v
AS-2.2-REALITY-GAP-PREP-001
        |
        |  unlock after v2.1.0 cert
        v
Future 2.2 Reality Gap intelligence surface (name TBD)
```

`ATLAS_2_1_RELEASE_CERTIFIED = NO`  
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`
