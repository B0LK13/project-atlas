# ADR-2.2-COMPAT-PIN-001 — Compatibility pin deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-COMPAT-PIN-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b431494` |
| Tree | `26a59cd` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-2 compat-pin PREP (PR #196) landed expectation / scenario stubs and base
negative sketches under `docs/atlas-2.2/compat-pin/`. Sibling deepen packages
(mem-gov, research, DoD, time-machine, reality-live) carry an explicit
forbidden-action schema and deepen negatives with fixture-only evidence walls.
Compat-pin lacked that sibling depth.

## Decision

1. Land a docs-owned `compat-pin-forbidden-action.schema.json` with an enum
   action vocabulary under `docs/atlas-2.2/compat-pin/contracts/`.
2. Add deepen negative fixtures that always set
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
3. Keep base expectation stubs and base negatives at their existing paths —
   no relocation or dual ownership.
4. Do **not** publish `docs/releases/2.1.0/` or mutate `compat_anchor.py`
   until unlock / 2.1 certification.

## Consequences

- Positive: compat-pin reaches sibling deepen artifact depth; clear fail-closed
  vocabulary for future implementers.
- Negative: no runtime pin module and no 2.1 anchor publication on this tip;
  fixtures grant no gate credit.

## Non-decisions

- Exact post-cert consumer migration order for intelligence packages
- Whether `atlas compat verify` gains a 2.1 mode before or with unlock
- Packaging of anchor JSON as package data vs docs-owned release artifact
