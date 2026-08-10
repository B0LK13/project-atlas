# Atlas 2.2 — Knowledge CI engine (PREP)

Status: **PREP ONLY** — architecture + fixtures + unit-test language drafts.
No production schema freeze. No runnable 2.2 engine.

Package: [`AS-2.2-KCI-ENGINE-PREP-001`](../AS-2.2-KCI-ENGINE-PREP-001.md)

## Documents

| Doc | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Engine layers, data flow, truth boundaries |
| [UNIT-TEST-LANGUAGE.md](UNIT-TEST-LANGUAGE.md) | Knowledge unit-test vocabulary draft |
| [FIXTURE-PLAN.md](FIXTURE-PLAN.md) | Reserved fixture families / scenarios |

Fixture inventory stub: [`../fixtures/kci-engine/README.md`](../fixtures/kci-engine/README.md)

## Relation to 2.0 / 2.1

```text
AS-2.0-KCI-001 (thin compile envelopes)
AS-2.0-KCI-HARNESS-001 (gate catalog ≠ promote)
        |
        |  PREP (this tree) — docs only
        v
AS-2.2-KCI-ENGINE-PREP-001
        |
        |  unlock after v2.1.0 cert
        v
AS-2.2-KCI-001 (GAP-NS-005) — future implementation
```

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`.
