# PREP — Migration strategy (1.0 → 2.0)

Status: **PREP ONLY**. No migration runners shipped.

## Principles

1. **1.0 wins** until RELEASE CERTIFIED and owner opens 2.0 packages
2. Compatibility snapshot pin required before 2.0 consumers
3. Additive packages preferred; no silent rewrite of authority planes
4. Fixture-first migration rehearsals; estate only after PILOT

## Phases (draft)

| Phase | Entry | Exit |
|---|---|---|
| A Prep | Track B docs | `2.0_PREP_COMPLETE_PENDING_1.0_ANCHOR` (docs) |
| B Anchor | 1.0 RELEASE + WEB + PILOT/waiver | certified snapshot pin |
| C Freeze | §98 + owner auth | IMPLEMENTATION READY may be considered |
| D Impl | READY=YES | first 2.0 package on production branch |

## Explicit

Phase A completion ≠ `ATLAS_2_0_IMPLEMENTATION_READY = YES`.
