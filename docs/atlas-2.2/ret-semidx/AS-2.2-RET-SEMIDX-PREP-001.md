# AS-2.2-RET-SEMIDX-PREP-001 — Semantic index contract prep (SAFE reserved stub)

| Field | Value |
|---|---|
| Package | **AS-2.2-RET-SEMIDX-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Reserved ID | `AS-2.2-RET-SEMIDX-001` (see [`PACKAGE-CONTRACT-STUBS.md`](../PACKAGE-CONTRACT-STUBS.md)) |
| Tip audited | `6dadf03324fba553e71052bd7ec2278eec9ea4f6` |
| Tree | `df0e327f5ec8a77d8c2bab5c2bc1c05154657600` |
| Scope | `docs/atlas-2.2/ret-semidx/**` (+ unique unit test) |
| Production mutation | **NONE** |
| Peer | `AS-2.2-RET-HYBRID-001` — **do not dual-own** hybrid fixtures |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Land the **reserved** semantic-index contract prep named in
[`PACKAGE-CONTRACT-STUBS.md`](../PACKAGE-CONTRACT-STUBS.md) (`AS-2.2-RET-SEMIDX-001`).
Semantic slot remains **disabled by default**; enabling without an index contract
fails closed. This PREP does **not** ship embeddings, vector stores, or Layer B
authority.

## Hard invariants

1. Semantic slot `enabled=false` by default.
2. Semantic hits never elevate to Layer B / claim authority.
3. No release / unlock / PILOT invent from this tree.
4. No dual-own of `fixtures/hybrid-retrieval/` or live `retrieval` module.
5. Demo VERIFIED ≠ release unlock / ≠ authentic PILOT PASS.

## Deliverables

| Doc | Role |
|---|---|
| [`CONTRACT.md`](CONTRACT.md) | Slot contract sketch |
| [`INVARIANTS.md`](INVARIANTS.md) | Fail-closed walls |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Negative inventory |
| [`contracts/ret-semidx-forbidden-action.schema.json`](contracts/ret-semidx-forbidden-action.schema.json) | Forbidden-action stub |
| [`fixtures/`](fixtures/) | Negative rehearsal payloads |
| [`adr/ADR-2.2-RET-SEMIDX-001-semantic-index-prep.md`](adr/ADR-2.2-RET-SEMIDX-001-semantic-index-prep.md) | Boundary ADR |

## Explicit non-claims

- Not editing `docs/atlas-2.2/README.md` from this package branch
- Not `ATLAS_2_1_RELEASE_CERTIFIED=YES`
- Not embeddings-as-authority product
- Fixture PASS ≠ authentic PILOT PASS
