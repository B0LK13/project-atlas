# Compatibility pin — package index

Status: **PREP ONLY** (pre-`v2.1.0` tip; unlock still post-cert). Docs /
contract stubs / fixtures. Production mutation: **NONE**. Gate credit: **NO**.
`ATLAS_2_1_RELEASE_CERTIFIED`: **NO**.

| Doc | Role |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Anchor layers + drift classes + truth boundaries |
| [CONTRACT.md](./CONTRACT.md) | FR/NFR stubs + operation shapes |
| [INVARIANTS.md](./INVARIANTS.md) | Hard fail-closed rules |
| [FIXTURE-PLAN.md](./FIXTURE-PLAN.md) | Fixture family reservation |
| [AS-2.2-COMPAT-PIN-PREP-001.md](./AS-2.2-COMPAT-PIN-PREP-001.md) | Package charter |
| [./contracts/](./contracts/) | Docs-only JSON Schema stubs |
| [./fixtures/](./fixtures/) | Synthetic sample payloads |
| [./adr/](./adr/) | Prep boundary ADR |

## Truth boundaries

```text
PREP EXPECTATION          ≠  PUBLISHED 2.1 ANCHOR
FIXTURE PIN SKETCH        ≠  v2.1.0 RELEASED
1.0 COMPAT VERIFY PASS    ≠  2.1 RELEASE CERTIFIED
CONSUMER DECLARATION      ≠  RUNTIME MUTATION
FIXTURE PASS              ≠  PILOT / RELEASE
```

## Unlock

Runtime work for `AS-2.2-COMPAT-PIN-001` remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0` certification.
`ATLAS_2_1_RELEASE_CERTIFIED` remains **NO** on this prep tip.
