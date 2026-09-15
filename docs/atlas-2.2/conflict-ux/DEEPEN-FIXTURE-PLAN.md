# Conflict UX — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive / disposition-negative payloads remain under
`docs/atlas-2.2/conflict-ux/fixtures/` (peer to `AS-2.2-CONFLICT-UX-PREP-001`).
Deepen negatives for certification / PILOT / LLM authority also live in that
directory and validate against `conflict-ux-forbidden-action.schema.json`.
**Gate credit: NO.** Runner: absent until post-unlock.

**DEMO VERIFIED ≠ release / PILOT.**

## Families

| Family | Path | Package |
|---|---|---|
| conflict-ux (base) | `docs/atlas-2.2/conflict-ux/fixtures/` FX-001..006 | AS-2.2-CONFLICT-UX-PREP-001 (peer) |
| conflict-ux deepen | same `fixtures/` FX-101..103 | AS-2.2-CONFLICT-UX-DEEPEN-PREP-001 |

Base disposition negatives (`auto_resolve`, `ui_canonical_write`,
`authority_elevation`) stay on `disposition-action.schema.json` — **do not
relocate**. Deepen forbidden-action negatives are additive.

## Deepen scenarios (negative)

| ID | File | Intent |
|---|---|---|
| FX-2.2-CUX-101 | `negative-release-cert-stamp.expect.json` | Release-cert stamp from cockpit rehearsal → rejected |
| FX-2.2-CUX-102 | `negative-pilot-invent.expect.json` | Invented PILOT / authentic estate → rejected |
| FX-2.2-CUX-103 | `negative-llm-authority.expect.json` | LLM authority stamp / winner → rejected |

## Peer base negatives (not relocated)

| ID | File | Schema owner |
|---|---|---|
| FX-2.2-CUX-004 | `negative-auto-resolve.expect.json` | `disposition-action` (base) |
| FX-2.2-CUX-005 | `negative-ui-write.expect.json` | `disposition-action` (base) |
| FX-2.2-CUX-006 | `negative-authority-elevation.expect.json` | `disposition-action` (base) |

## Rules

- `evidence_class = fixture-only`
- `authentic_estate = false`
- `release_certified = false`
- `pilot_pass = false`
- `canonical_writes = false`
- `pilot_roots = 0`
- Synthetic relative ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- Never mutate runtime `conflict_projections` from fixture success
- Do not relocate or rewrite base disposition / cockpit fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-CUX-101..103 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
