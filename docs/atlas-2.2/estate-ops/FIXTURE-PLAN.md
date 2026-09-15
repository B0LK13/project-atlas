# Estate Ops — fixture plan (PREP)

Package: **AS-2.2-ESTATE-OPS-PREP-001**  
Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/estate-ops/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| estate-ops | `docs/atlas-2.2/estate-ops/fixtures/` | AS-2.2-ESTATE-OPS-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-EO-001 | `cockpit-estate-selected.sample.json` | Full cockpit with harbor demo estate slice |
| FX-2.2-EO-002 | `mission-control-lens.sample.json` | Mission Control lens card |
| FX-2.2-EO-003 | `ops-health-receipt.sample.json` | Ops health receipt (unknown rollup) |
| FX-2.2-EO-004 | `negative-unknown-as-healthy.expect.json` | unknown→healthy → rejected |
| FX-2.2-EO-005 | `negative-ui-canonical-write.expect.json` | canonical_write → rejected |
| FX-2.2-EO-006 | `negative-pilot-invent.expect.json` | pilot_invent → rejected |
| FX-2.2-EO-DEEPEN-101 | `negative-deepen-unknown-as-healthy.expect.json` | deepen forbidden-action |
| FX-2.2-EO-DEEPEN-102 | `negative-deepen-ui-canonical-write.expect.json` | deepen forbidden-action |
| FX-2.2-EO-DEEPEN-103 | `negative-deepen-pilot-invent.expect.json` | deepen forbidden-action |
| FX-2.2-EO-DEEPEN-104 | `negative-deepen-ops-runtime-mutation.expect.json` | deepen forbidden-action |
| FX-2.2-EO-DEEPEN-105 | `negative-deepen-llm-authority.expect.json` | deepen forbidden-action |

Deepen contract stub: `contracts/estate-ops-forbidden-action.schema.json`
(peer to base `estate-ops-action.schema.json`; do not dual-own).

All deepen negatives: `evidence_class=fixture-only`, `authentic_estate=false`,
`release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic `harbor-*` demo project ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `ops_health` from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-EO-001..006 | payload-present (docs sketch) | **NO** |
| FX-2.2-EO-DEEPEN-101..105 | payload-present (deepen sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
