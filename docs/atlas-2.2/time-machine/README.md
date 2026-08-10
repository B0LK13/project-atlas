# Knowledge Time Machine — package index

Status: **PREP ONLY** (pre-`v2.1.0`). Docs / contract stubs / fixtures.
Production mutation: **NONE**. Gate credit: **NO**.

| Doc | Role |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | As-of + T1–T2 layers, truth boundaries |
| [CONTRACT.md](./CONTRACT.md) | FR/NFR stubs + operation shapes |
| [FIXTURE-PLAN.md](./FIXTURE-PLAN.md) | Fixture family reservation |
| [../AS-2.2-TIME-MACHINE-001.md](../AS-2.2-TIME-MACHINE-001.md) | Package charter |
| [./contracts/](./contracts/) | Docs-only JSON Schema stubs |
| [./fixtures/](./fixtures/) | Synthetic sample payloads |

## Truth boundaries

```text
TIME MACHINE AS-OF  ≠  AUTHORITY
TIME MACHINE DIFF   ≠  LAYER B MUTATION
GRAPH DIFF          ≠  AUTHORITY
DECISION DIFF       ≠  HUMAN APPROVAL
WALL-CLOCK NOW      ≠  VALID-TIME INPUT
FIXTURE PASS        ≠  PILOT / RELEASE
```

## Unlock

Runtime work remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0` certification.
