# AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001

Current-main guard so `atlas context` / handoff packs cannot look current
when connect inventory is STALE or UNKNOWN.

Does **not** retarget historical `#380`. That tip implemented a second
frozen-fingerprint engine (`context_stale_guard.py`). This package reuses
`project_atlas.inventory_drift` already on `main` (`#407`).

## Authorized production scope

- `src/project_atlas/agent_handoff.py`
- `src/project_atlas/cli.py` (freshness line on `atlas context`)
- tests + this doc

Out of scope: the six shared drift lenses (`#414` conflict set),
`project_changed.py` / `project_brief.py` (`#418`), inventory-drift engine
changes, inbox list/API, Obsidian, billed-model runs.

## Contract

- Missing manifest, missing/rejected `source_root`, or no project-scoped
  hashed sources → `UNKNOWN`, never FRESH
- Live hashed sources drifted from `generated/ops/connect-manifest.json` →
  `STALE`
- Honesty always: `stale_is_current=false`, `unknown_is_fresh=false`,
  `fresh_is_authority=false`, `lens_is_authority=false`
- `source_inventory_stale=true` only when status is `STALE`
- Markdown banner + suggested-next prefix when STALE/UNKNOWN
- `atlas handoff resume` re-evaluates live inventory drift (no second hash
  walk). A pack written FRESH becomes STALE after a disk edit against the
  same connect-manifest
- Writes stay under `generated/ops/agent-context` and
  `generated/ops/handoffs`. Layer B (`projects/`) is not rewritten by this
  guard

## Honesty

- `CONTEXT_FRESHNESS != AUTHORITY`
- `STALE != CURRENT`
- `UNKNOWN != FRESH`
- `FRESH inventory != Truth Core`
- `DEMO_FIXTURE != AUTHENTIC_PILOT`
- `MERGE_AUTHORIZATION = NOT_GRANTED`
