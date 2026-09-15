# Handoff — AS-TASK-CONTEXT-AND-CONTINUITY-001

## For task-contract owner (ATLAS-BACKLOG-TO-TASK-CONTRACT-001)

- Consume path: pass contract JSON to `atlas task-context compose --contract`.
- When `project_atlas.orchestration.taskcontract` is importable, the live loader
  maps `TaskContract` → `ContractSnapshot` automatically.
- Content digest of the packet includes `contract_digest`; contract edits change
  packet identity.

## For work-readiness / handoff owner (ATLAS-WORK-READINESS-AND-HANDOFF-001)

- Use `atlas task-context export --view reviewer` and `continuation` as
  readiness/handoff *inputs*.
- Continuation explicitly sets `continuation_authorizes_launch/replay/reset=false`.
- Freshness recheck belongs at prepare/handoff (`task-context freshness`).

## For execution-quality owner (ATLAS-EXECUTION-QUALITY-LOOP-001)

- Evidence bundle shape: `tests/fixtures/task-context-continuity/evidence/bundle.json`.
- Hypothesis recorded (unproven, zero model calls): smaller task packets *may*
  improve agent performance — candidate follow-on experiment only.
  See `docs/evidence/AS-TASK-CONTEXT-AND-CONTINUITY-001/demo/size-comparison.json`.

## Demo artifacts

Under `docs/evidence/AS-TASK-CONTEXT-AND-CONTINUITY-001/demo/`:

- `packet.json`, `inspect.json`, `budget.json`, `continuation.json`
- `freshness-after-change.json` (controlled architecture.md mutation)
- `size-comparison.json`
- `HEAD.txt` / `TREE.txt` (update after commit)

## Non-claims

No push, merge, self-IV, registry reassignment, or spending changes were performed.
