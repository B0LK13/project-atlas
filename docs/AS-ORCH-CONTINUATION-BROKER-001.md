# AS-ORCH-CONTINUATION-BROKER-001

```
PACKAGE = AS-ORCH-CONTINUATION-BROKER-001
BACKEND = CURSOR_STOP_HOOK_FOLLOWUP
REUSES = AS-ORCH-001D + AS-ORCH-001E
SECOND_GOVERNOR = FORBIDDEN
SECOND_DISPATCHER = FORBIDDEN
PR400_CONSUMED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

Lifecycle continuation for a primary-governor `CHECKPOINT_CONTINUE`.
Not task-decision authority. Not merge authority.

## Backend

The only real same-chat successor transport is the documented Cursor
stop-hook `followup_message`. This package binds a durable consume-once
`GOVERNOR_CYCLE_ID` store to that hook.

It does **not** invent a parent-conversation API, consume the 001C
single-slot handoff (PR400 leftover), or auto-dispatch 001D hops.

`governor-loop-tick` (001E) remains the in-process tick. Resource
exhaustion enqueues `RESOURCE_YIELD` instead of `OWNER_REQUIRED`.

## Invariants

- One primary governor
- At most one unconsumed successor per pin
- Stale main/tree checkpoints fail closed
- Foreign `repository_identity` fail closed
- Worker/session terminal ≠ DAG terminal
- Owner-gate fingerprint emits at most one prompt
- Stop-event extras never interpolate into followup text
- Followup cannot grant merge, execution, or authority
- `CHECKPOINT_CONTINUE` is exposed only after `finalize_governor_checkpoint` durably queues a successor
- Atlas does not treat Cursor `loop_count > 0` as DAG-terminal
- Project stop hook sets `loop_limit: null`; Atlas no-progress bound is 3 identical cycles
- `beforeSubmitPrompt` consumes an exact trusted follow-up; untrusted text cannot consume a foreign cycle
- Cursor hooks bind current worktree `src` before any `project_atlas` import
- If `OWNER_ACTION_REQUIRED_NOW = NO` and safe DAG work remains, a final response requires successor `QUEUED`, `FOLLOWUP_EMITTED`, or `AWAITING_RESULT`
- `NEXT_MACHINE_ACTION = X` is invalid unless X is executing or durably scheduled
