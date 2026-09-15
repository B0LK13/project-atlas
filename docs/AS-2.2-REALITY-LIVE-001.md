# AS-2.2-REALITY-LIVE-001 — Live Reality Gap collectors (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-REALITY-LIVE-001** |
| Phase | **PREP** (pre-`v2.1.0` — contracts / fixtures / design only) |
| Status | **READY for unlock** after `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` |
| Class | **DOCUMENTATION + FIXTURE** — no production mutation |
| Predecessor | `AS-2.0-REALITY-GAP-001` (static 1.0→2.0 fixture inventory) |
| Directive context | `D-PROJECT-ATLAS-2.1-PRODUCTIONIZATION-001` + 2.2 north-star prep |
| Compat note | Does **not** change 2.1 runtime defaults or Core authority |

## Purpose

Design **live, plane-aware Reality Gap collectors** that compare declared Atlas
maturity (board / matrix / package cards) against observable evidence across
four planes:

1. **Conversational** — dialogue / agent / Ask / ChatGPT-export evidence
2. **Documentary** — OKF notes, plans, ADRs, package docs
3. **Implementation** — code modules, CLI/API/MCP surfaces, tests
4. **Operational** — live receipts, ops events, supervised runtime signals

Prep ships design + schema drafts + fixtures only. Runtime collectors unlock
only after `v2.1.0` certification.

## Surfaces (this PREP)

| Surface | Path |
|---|---|
| Lane index | `docs/atlas-2.2/reality-live/README.md` |
| Collectors design | `docs/atlas-2.2/reality-live/COLLECTORS-DESIGN.md` |
| Planes contract | `docs/atlas-2.2/reality-live/PLANES.md` |
| Schema drafts | `docs/atlas-2.2/contracts/reality-live/` |
| Fixtures | `docs/atlas-2.2/reality-live/fixtures/` |
| Prep gate test | `tests/unit/test_as_2_2_reality_live_prep_001.py` |

## Relationship to AS-2.0-REALITY-GAP-001

| | AS-2.0-REALITY-GAP-001 | AS-2.2-REALITY-LIVE-001 |
|---|---|---|
| Scope | Named 1.0→2.0 theme gaps | Multi-plane live honesty vs claimed maturity |
| Evidence | Static fixture catalog | Collectors over live-read + fixture corpora |
| Output | `reality-gap-inventory` | `reality-live-gap-report` (draft) |
| Estate invent | Forbidden (`pilot_roots=0`) | Forbidden (same invariant) |
| Authority | Derived / fixture-only | Derived / never Layer B authority |

## Invariants (carry forward + extend)

- `pilot_roots = 0` / `invent_pilot_roots = false`
- `authentic_estate = false` unless owner-gated authentic PILOT evidence exists
- Collectors are **read-only**; never write Layer A/B canonical notes
- Collectors never stamp `WEB ACCEPTED`, `RELEASE`, or `ATLAS_2_1_RELEASE_CERTIFIED`
- UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy
- LLM / conversational evidence ≠ authority (quarantine-first)
- Prep does **not** mutate `src/project_atlas/**` production modules

## Explicit non-claims

- Not authentic estate PILOT PASS
- Not a substitute for `AS-2.1-PILOT-AUTH-001`
- Not LIVE runtime collectors until post-`v2.1.0` implementation package
- Fixture success ≠ productionization complete

## Unlock gate

```text
v2.1.0 certified
  → ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED
  → AS-2.2-REALITY-LIVE-001 (implementation)
```

Until then: architecture / contracts / fixtures only.
