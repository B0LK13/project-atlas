# AS-STUDIO-A0-001 — evidence

```text
STUDIO_UI != AUTHORITY
PREP != IMPLEMENTED  (this file records lane implementation evidence only)
MERGE_AUTHORIZATION = NOT_GRANTED
```

Filled after validation commands in the `studio-a0` worktree
(`feat/as-studio-a0-001`, 2026-09-09).

## Commands

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a0.py -q --tb=short
.venv/bin/python -m ruff check scripts/atlas_studio tests/unit/test_atlas_studio_a0.py
.venv/bin/python scripts/atlas-studio.py snapshot --json
.venv/bin/python -m pytest tests/unit/test_atlas_dag_control_view.py tests/unit/test_atlas_dag_telemetry.py -q --tb=line
```

## Results

| Check | Result | Notes |
|---|---|---|
| `test_atlas_studio_a0.py` | **PASS** (11 passed) | injected builders; no subprocess protocol |
| ruff `atlas_studio` + test | **PASS** | All checks passed |
| `atlas-studio doctor --json` | **PASS** (exit 0) | imports + honesty + schema ok |
| `atlas-studio snapshot --json` | **PASS** (exit 0, ~72s live) | live GhClient → control_view/telemetry panels populated |
| control_view + telemetry regression | **PASS** (28 passed) | no breakage from A0 reuse |

## Tree inventory (implementation)

See `REUSE-MAP.md`. New paths: `docs/atlas-3/studio/a0/`,
`docs/adr/ADR-034-studio-daemon-authority.md`,
`schemas/atlas_studio_*.schema.json`, `scripts/atlas_studio/`,
`scripts/atlas-studio.py`, `tests/unit/test_atlas_studio_a0.py`.
A0-BRIEF status → `IMPLEMENTED_IN_LANE`.
