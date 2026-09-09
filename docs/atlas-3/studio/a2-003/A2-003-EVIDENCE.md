# AS-STUDIO-A2-003 — evidence

```text
AS_STUDIO_A2_003 = IMPLEMENTED_IN_LANE
CI_PASS != FORMAL_IV · IMPLEMENTED != MERGED · TASK_CONTEXT != AUTHORITY
```

| Field | Value |
|---|---|
| Branch | `feat/as-studio-a5-task-context-001` |
| Base | #785 `feat/as-studio-a2-002-mission-journey` @ `cd4523fc588ac941b13ad75731624039e572ba71` |
| HEAD | pinned by the evidence-tip commit after exact-head CI |
| Module | `scripts/atlas_studio/task_context.py` |
| CLI | `atlas-studio task-context --lane pr/N [--agent] [--vault --project] [--with-agent-context] [--mc-file --matrix-file --stacks-file] [--json]` |
| Schema | `schemas/atlas_studio_task_context_v1.schema.json` |
| Doctor | `a2_003_task_context` |
| Tests | `tests/unit/test_atlas_studio_a2_003_task_context.py` |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a0.py tests/unit/test_atlas_studio_a1_*.py \
  tests/unit/test_atlas_studio_a2_*.py -q --no-cov
# Ruff: the repo config includes only src/** and tests/** (#774); scripts are linted by explicit path
.venv/bin/python -m ruff check scripts/atlas_studio/task_context.py scripts/atlas_studio/cli.py \
  tests/unit/test_atlas_studio_a2_003_task_context.py
.venv/bin/python scripts/atlas-studio.py doctor --json
```

## Non-claims

No formal IV. Not merged. Not on main. Live path exercised only against fakes in
tests; a live run needs `gh` and a registered agent id. `#785` base is itself
unmerged and un-verified; this package inherits none of its status.
