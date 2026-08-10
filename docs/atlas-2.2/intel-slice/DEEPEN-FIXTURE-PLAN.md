# Intelligence slice — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive / negative payloads remain under
`docs/atlas-2.2/intel-slice/fixtures/` (peer to `AS-2.2-INTEL-SLICE-PREP-001`).
Deepen negatives for certification / PILOT / LLM authority also live in that
directory and validate against `intel-slice-forbidden-action.schema.json`.
**Gate credit: NO.** Runner: absent until post-unlock.

**DEMO VERIFIED ≠ release / PILOT.**

## Families

| Family | Path | Package |
|---|---|---|
| intel-slice (base) | `docs/atlas-2.2/intel-slice/fixtures/` FX-001..007 | AS-2.2-INTEL-SLICE-PREP-001 (peer) |
| intel-slice deepen | same `fixtures/` FX-101..103 | AS-2.2-INTEL-SLICE-DEEPEN-PREP-001 |

Base negatives (`authority_elevation`, `silent_conflict_resolve`,
`llm_authority`, `canonical_write`) stay as informal base expect JSON — **do not
relocate**. Deepen forbidden-action negatives are additive.

## Deepen scenarios (negative)

| ID | File | Intent |
|---|---|---|
| FX-2.2-ISL-101 | `negative-release-cert-stamp.expect.json` | Release-cert stamp from slice rehearsal → rejected |
| FX-2.2-ISL-102 | `negative-pilot-invent.expect.json` | Invented PILOT / authentic estate → rejected |
| FX-2.2-ISL-103 | `negative-llm-authority-stamp.expect.json` | LLM authority stamp / winner → rejected |

## Peer base negatives (not relocated)

| ID | File | Owner |
|---|---|---|
| FX-2.2-ISL-004 | `negative-authority-elevation.expect.json` | base PREP-001 |
| FX-2.2-ISL-005 | `negative-silent-conflict-resolve.expect.json` | base PREP-001 |
| FX-2.2-ISL-006 | `negative-llm-authority.expect.json` | base PREP-001 |
| FX-2.2-ISL-007 | `negative-canonical-write.expect.json` | base PREP-001 |

## Rules

- `evidence_class = fixture-only`
- `authentic_estate = false`
- `release_certified = false`
- `pilot_pass = false`
- `canonical_writes = false`
- `status = rejected_forbidden`
- `pilot_roots = 0`
- Synthetic relative ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- Never mutate runtime from fixture success
- Do not relocate or rewrite base sample / negative fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-ISL-101..103 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
