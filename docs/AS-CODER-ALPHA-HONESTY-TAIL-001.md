# AS-CODER-ALPHA-HONESTY-TAIL-001

Current-main tail for unique `#384` What Changed honesty and `#382` brief-follows-next honesty.

Does **not** re-wire the six shared drift lenses. Those belong to `#414`
(`OWNER_HELD_CANONICAL` under D-049). `#409` is the `SUPERSEDE_CANDIDATE`
for that shared set.

## Authorized production scope

- `src/project_atlas/project_changed.py`
- `src/project_atlas/project_brief.py`
- tests + this doc

Out of scope: `project_state.py`, `project_unknown.py`, `attention_hygiene.py`,
`project_decisions.py`, `source_health.py`, `project_next.py`.

## #384

When the historical inventory diff is `UNCHANGED` and live connect inventory is
`STALE`:

- `rollup` may remain `unchanged` (no invented history)
- `honesty.unchanged_is_current = false`
- `honesty.stale_is_current = false`
- `honesty.lens_is_authority = false`

Uses `project_atlas.inventory_drift` already on main. No second engine.

## #382

Brief copies Next honesty when present:

- `NEXT.answer_evidence_stale` → brief exposes `answer_evidence_stale` and
  `STALE EVIDENCE != CURRENT`
- `NEXT.live_source_unverified` → brief exposes the flag and must not summarize
  Next as current or healthy

`BRIEF != authority`. No Layer B write beyond existing brief materialization.

## Conflict set

Do not merge `#409` and `#414`. Shared six-lens canonical path is `#414`.
This tail carries only the unique `#384`/`#382` honesty that `#414` correctly
left out of scope.
