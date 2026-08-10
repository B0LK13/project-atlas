# Atlas 2.2 — prep index (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — architecture / contracts / fixtures |
| Unlock event | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (fires after `v2.1.0`) |
| Production semantic mutation | **FORBIDDEN** on this tip |
| Baseline tip | `a1e0972a18608487f71c6979e454247df52d2e44` / TREE `c6cfe95ffe7d3c1699459f620aadf112c66a8524` |
| Evidence lane | `atlas-2.1-productionization-001` |

## Purpose

Hold Atlas 2.2 **north-star intelligence** prep packs that do not change Core
authority semantics, runtime defaults, or production schemas under `src/`.

Roadmap: [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md).

## Packages in this tree (prep)

| Package | Theme | Path |
|---|---|---|
| **AS-2.2-CTX-COMPILER-001** | Task-specific Context Compiler | [`ctx-compiler/`](./ctx-compiler/) |

## Firewall

- Static `AS-2.0-CTX-001` context packs ≠ full Context Compiler.
- Docs/ADR/fixtures here do **not** unlock production implementation.
- No invent markers / no authentic PILOT from fixtures.
