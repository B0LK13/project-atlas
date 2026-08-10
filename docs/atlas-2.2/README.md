# Atlas 2.2 — prep tree (additive)

| Field | Value |
|---|---|
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** (awaits `v2.1.0`) |
| Prep policy | Docs / contracts / fixtures / ADRs only |
| Production mutation | **FORBIDDEN** on this branch |

## Packages seeded here

| Package | Directory | Status |
|---|---|---|
| AS-2.2-MEM-GOV-001 | `mem-gov/`, `contracts/mem-gov/`, `fixtures/mem-gov/`, `adr/ADR-2.2-MEM-GOV-001-*` | **PREP** |

Sibling 2.2 prep PRs may add other directories under this tree. Do not treat presence of this README as charter freeze or implementation unlock.

## Invariants

- No `src/` / package-data schema promotion from these stubs
- No tip-pin edits to `docs/atlas-2.1/PACKAGE-BOARD.md` in prep PRs
- Fixture PASS ≠ authentic PILOT PASS
- Agent memory ≠ Layer B authority
