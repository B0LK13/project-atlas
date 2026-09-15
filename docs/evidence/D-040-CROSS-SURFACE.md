# D-040 — Cross-surface consistency + human truth loop v2

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-040
**Branch:** cursor/coder-alpha-040-arch-consistency-d039

## Cross-surface brief consistency

Integration: `tests/integration/test_cross_surface_consistency_d040.py`

After `atlas connect` on a small fixture project, disk authority
`generated/ops/project-brief-<id>.json` is compared for:

- `purpose`
- `current_state`
- `architecture_summary`
- `recent_meaningful_changes`
- `important_decisions`
- `unknown_or_conflicting`

Surfaces checked (string equality):

| Surface | API |
|---|---|
| Disk brief | `generated/ops/project-brief-<id>.json` |
| Web | `web_api.brief.read_project_brief` |
| Obsidian living note | `materialize_obsidian_projection(..., refresh_brief=False)` + section parse |
| Agent context | `export_agent_context(..., refresh_brief=False)` → `brief` field |

Honesty stamp: `honesty.atlas_opt_wake_gate == CLOSED` on disk, web, and agent exports.

## Human truth loop v2

Integration: `tests/integration/test_human_truth_loop_v2_d040.py`

Flow:

1. Connect fixture → pending review exists
2. `human_loop.apply_review_decision` accept
3. Rematerialize `materialize_unknown_lenses` + `materialize_project_briefs`
4. Pending count drops; `state/human-decisions/<id>.json` records decision
5. Re-run `materialize_unknown_lenses` + `build_project_brief(refresh=True)` — decided item stays `resolved`, does not resurrect as pending

## Non-claims

```
DEMO_FIXTURE != AUTHENTIC_PILOT
DEMO != RELEASE
UI != CANONICAL_TRUTH
MODEL_OUTPUT != AUTHORITY
CODEX_VALIDATED = NO
EXTERNAL_SECURITY_REVALIDATION_REQUIRED = YES
ATLAS_OPT_WAKE_GATE = CLOSED
```
