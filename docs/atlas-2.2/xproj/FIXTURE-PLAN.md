# Cross-project fabric — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/xproj/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| xproj | `docs/atlas-2.2/xproj/fixtures/` | AS-2.2-XPROJ-CONTRACT-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-XPROJ-001 | `fabric-inventory.fixture.json` | Full inventory envelope citing AS-XPROJ-* buckets |
| FX-2.2-XPROJ-002 | `entity-join.sample.json` | Explicit entity + join citation (conceptual) |
| FX-2.2-XPROJ-003 | `cross-project-edge.sample.json` | Explicit edge spanning two projects |
| FX-2.2-XPROJ-004 | `duplicate-candidate.sample.json` | Candidate with `autocollapse: false` |
| FX-2.2-XPROJ-005 | `conflict-index.sample.json` | Derived conflict + index refs (≠ RET-001) |
| FX-2.2-XPROJ-006 | `negative-fuzzy-join.expect.json` | Fuzzy join → quarantine expect |
| FX-2.2-XPROJ-007 | `negative-autocollapse.expect.json` | UUID rewrite → reject expect |
| FX-2.2-XPROJ-008 | `negative-authority-elevate.expect.json` | Authority elevate → reject expect |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `atlas_2_1_release_certified = false`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never dual-own AS-XPROJ emit paths from fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-XPROJ-001..008 | payload-present (docs sketch) | **NO** |

Promotion to `fixtures/atlas-2.2/` + harness requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
