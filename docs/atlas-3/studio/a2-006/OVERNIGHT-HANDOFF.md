# Overnight handoff — ATLAS-STUDIO-OVERNIGHT-CONTINUATION-001

```text
GENERATED_FOR             = morning resume
MERGE_AUTHORIZATION       = NOT_GRANTED
FORMAL_IV_791             = NOT_STARTED
TASK_CONTEXT_786          = UNAVAILABLE (do not take over)
OBSERVATION_API           = UNAVAILABLE (explicit; do not invent)
```

## #791 refresh (one-shot; do not re-poll unchanged)

| Ref | Value |
|---|---|
| Tip at overnight start | `b9fd932d` |
| Prior behavioral candidate | `1bca04e3` (CI cancelled by later pushes; **no SUCCESS exact-head**) |
| Tip after overnight increment | see git tip on `feat/as-studio-a2-006-mission-session` |
| Exact-head CI SUCCESS | **NONE yet** for current tips (dependency recorded) |
| Formal IV | NOT_STARTED — packet under `iv/A2-006-FORMAL-IV-REQUEST-PACKET.md` |

## Completed this overnight cycle

1. Shared `snapshot_load.load_json_snapshot` — single read → byte SHA-256 → parse same buffer.
2. Continuity/action-evidence/mission-session use it; `CORRUPT` / `CORRUPT_INPUT` states.
3. Provenance honesty: byte hashes identify parsed bytes; multi-file consistency = binding checks (not a FS transaction).
4. CLI `mission-session` exit codes: 0 clear / 1 recovery / 3 persistence-interrupted.
5. Journey file load fail-closed via snapshot.
6. Regression tests for corrupt JSON, byte-hash equality, exit codes, no second-read drift.

## Validation

```text
Local studio suite (A* + snapshot_load): run at commit time
Independent verification: NOT_STARTED
CI exact-head: PENDING (external)
Merge: NOT_GRANTED
```

## Pending (engineering)

- Corrupt empty-file / UTF-16 edge cases if product needs them.
- Optional schema validate-on-load for intent/decision (soft) without inventing authority.
- When #786 lands: flip task-context AVAILABLE.
- Freeze tip only after exact-head CI SUCCESS; owner dispatches Formal IV.

## Owner / external blockers

- Exact-head CI SUCCESS on a frozen tip
- Formal IV dispatch
- Merge authorization
- #786 / #781 / stack consolidation

## Next command for resume

```bash
cd /home/gebruiker/Projects/project-atlas-worktrees/studio-a2-006-session
git fetch origin && git status -sb && git rev-parse HEAD
# If CI green on tip: pin CI_EXACT_HEAD once in A2-006-EVIDENCE (no retip loop)
# Else continue pending engineering list above
```
