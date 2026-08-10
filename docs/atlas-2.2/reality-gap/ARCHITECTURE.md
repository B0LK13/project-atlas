# Reality Gap — architecture (PREP)

Package: **AS-2.2-REALITY-GAP-PREP-001**  
Status: **PREP ONLY** — non-normative until 2.2 unlock + contract freeze.

## Problem

Atlas 2.0 ships a **fixture-only** Reality Gap inventory
(`AS-2.0-REALITY-GAP-001`) and a read-only UI catalog
(`AS-2.0-REALITY-GAP-UI-001`). Operators still need a 2.2-facing register that:

- names remaining gaps against north-star / 2.2 intelligence themes
- keeps unknown / blocked / partial statuses **honest** (never “healthy”)
- keeps UI panels as **derived lenses** (never canonical writers)
- refuses to invent PILOT roots or stamp release credit from fixtures

## Design sketch

```text
  REALITY-GAP.md / gap register rows
              |
              v
     ┌────────────────────┐
     │ prep inventory     │  scenarios[] + invariants
     │ (docs fixtures)    │
     └────────────────────┘
              |
      +-------+-------+
      |               |
      v               v
 UI catalog         Ops JSON
 (read-only)     (derived only)
 UI≠canonical    never Layer B
```

Future runtime (post-unlock) may emit derived artifacts under a vault path such
as `generated/ops/reality-gap/` — **consume-only**, authority `derived`.

## Compiler / inventory rules (fail-closed)

1. **Coverage** — every documented gap_id appears exactly once in the inventory.
2. **Evidence class** — prep scenarios stay `fixture-only` until an authorized
   live-read / pilot class is introduced by a later package.
3. **No invention** — absent estate / missing pilot ⇒ blocked or open; never
   synthesize PASS / READY / healthy.
4. **unknown ≠ healthy** — status `unknown`, missing health signals, or
   unresolved blockers never coerce to healthy / addressed.
5. **UI ≠ canonical** — UI catalogs set `canonical_writes=false` and
   `read_only=true` on every panel; no Layer B writes.
6. **no PILOT invent** — `pilot_roots=0`, `invent_pilot_roots=false`,
   `authentic_estate=false` on every scenario.
7. **Determinism** — JSON `sort_keys=True`; no wall-clock in bodies (NFR-001).

## Scenario status vocabulary (prep)

| Status | Meaning | May claim healthy? |
|---|---|---|
| `open` | Gap acknowledged; no durable mitigation | **no** |
| `partially-addressed` | Contract / fixture / bounded surface only | **no** |
| `blocked-pilot` | Requires authentic PILOT / waiver | **no** |
| `blocked-freeze` | Requires contract freeze / owner auth | **no** |
| `addressed-fixture-only` | Fixture rehearsal green; not production | **no** |
| `unknown` | Insufficient evidence to classify | **no** (unknown≠healthy) |

## Relationship to existing substrate

| Substrate | Relationship |
|---|---|
| `project_atlas.reality_gap` | 2.0 inventory — **do not mutate in this PREP** |
| `project_atlas.reality_gap_ui` | Read-only panels — UI≠canonical preserved |
| `docs/atlas-2.0/REALITY-GAP.md` | Conceptual source for gap_ids |
| Gap register / 2.2 roadmap | Planning context only; not cert |

## Out of scope (this prep)

- Python module changes under `src/project_atlas/`
- Shipping JSON Schema as package data
- CLI / API / MCP / web mutations
- Relabeling fixture PASS as PILOT / RELEASE / 2.1 CERTIFIED

## Promotion gate (future)

Implementation opens only after:

1. `ATLAS_2_1_RELEASE_CERTIFIED` path completes to `v2.1.0`
2. `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
3. Contract freeze checklist for Reality Gap prep stubs
