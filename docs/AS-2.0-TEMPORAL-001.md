# AS-2.0-TEMPORAL-001 — Bitemporal claim validity windows

| Field | Value |
|---|---|
| Package | **AS-2.0-TEMPORAL-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (contract deepen) |
| Class | **RWC** — builds on AS-CORE-005; fail-closed |
| Compat | `atlas-1.0.0-compat` |

## Purpose

Deepen AS-CORE-005 with explicit **valid-time** windows and fail-closed
**as-of** selection. Knowledge-time remains compilation-bound. Prefer
unresolved over a wrong current selection.

## Surfaces

| Surface | Path |
|---|---|
| Schemas | `claim-validity-window`, `claim-validity-catalog`, `bitemporal-as-of-result` |
| Module | `project_atlas.bitemporal` |
| Vault output | `generated/ops/bitemporal/<catalog>-validity-catalog.json` |

## Invariants

- No wall-clock `now` / `today` as valid-time or as-of input
- Inverted windows (`valid_to` < `valid_from`) reject
- Overlapping covers → `unresolved_overlap` (no silent winner)
- `evidence_kind=unknown` alone never selects current
- Claim Identity v2 unchanged; CORE-005 evaluator not rewritten
- Bound to compatibility anchor; **1.0 wins** conflicts

## Non-claims

- Not a full bitemporal database
- Not authority resolution (AS-CORE-006)
- Not query API rewrite
- Not Atlas 2.0 RELEASE CERTIFIED
