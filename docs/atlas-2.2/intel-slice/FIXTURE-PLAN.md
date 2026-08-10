# Intelligence slice — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/intel-slice/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| intel-slice | `docs/atlas-2.2/intel-slice/fixtures/` | AS-2.2-INTEL-SLICE-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-ISL-001 | `intel-slice-complete.sample.json` | Composed slice with all input families cited |
| FX-2.2-ISL-002 | `intel-slice-incomplete.sample.json` | Incomplete slice with `unknown[]` leftovers |
| FX-2.2-ISL-003 | `inputs-citations.sample.json` | Cite-only upstream id inventory |
| FX-2.2-ISL-004 | `negative-authority-elevation.expect.json` | authority elevation → rejected |
| FX-2.2-ISL-005 | `negative-silent-conflict-resolve.expect.json` | silent conflict resolve → rejected |
| FX-2.2-ISL-006 | `negative-llm-authority.expect.json` | LLM-as-authority → rejected |
| FX-2.2-ISL-007 | `negative-canonical-write.expect.json` | canonical write from slice → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `authority.level = derived`
- `canonical_write = false`
- Synthetic relative paths / ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- `generated` may include `by` only — never wall-clock `at`
- Never mutate runtime from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-ISL-001..007 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
