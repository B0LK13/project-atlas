# AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001

| Field | Value |
|---|---|
| Package | `AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001` |
| Module | `src/project_atlas/context_stale_guard.py` |
| Hook | `src/project_atlas/agent_handoff.py` |
| Tests | `tests/unit/test_as_coder_alpha_context_stale_guard_001.py` |

## Purpose

A later agent must not treat a previously exported context/handoff pack as
current when sources have changed. Missing inventory is `UNKNOWN`, never a
fabricated `FRESH`.

## Honesty

```
FRESHNESS != TRUTH CORE
STALE != HEALTH SCORE
UNKNOWN != FRESH
DEMO_FIXTURE != AUTHENTIC_PILOT
CONNECT_PY_REWRITTEN = NO
CLI_PY_TOUCHED = NO
```

## Behavior

- Export stamps a live source fingerprint into the context JSON and markdown.
- Resume rehashes files under the recorded `source_root` and compares.
- Disk edit without reconnect → `STALE` + `changed_paths`.
- Sibling `likely_project` rows do not make another project look `FRESH`.
- No Layer B / Truth Core writes beyond existing context/handoff ops files.
