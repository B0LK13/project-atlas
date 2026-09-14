# Migration and rollback

`AUTOMATIC_MIGRATION = NOT_IMPLEMENTED` · `CHECKPOINT_READER_SCHEMA = 2`

Adding continuation directories does not guarantee that every old/new binary
can read the same state. Preserve records and exact reader/writer revisions;
never delete or relabel a checkpoint to make a release accept it.

## Explicit layout and boundary

Use an operator-approved absolute `<G>` (for example `/srv/atlas`) containing
sibling `state/`, `queue/`, `programs/`, `worktrees/`, `checkout/` and `registry/`.
Here `<S>` = `<G>/state`, `<Q>` = `<G>/queue`, `<P>` =
`<G>/programs/approved.json`. Replace placeholders before running commands.
G must not be `/` or the current account's home directory; no component may be
a symlink/reparse point. State must not be inside a workspace. Pass
`--governed-root <G>` rather than broadening defaults.

```text
<S>/.atlas/orchestration/program/
    state.json
    events.jsonl
    launches/
    envelopes/
    checkpoints/
    decisions/
    dispatcher/
```

Queue data is under Q, which may differ from S. Keep every queue-referenced
state root, approved program bytes, workspace evidence and registry binding
together in a quiescent backup. There is no automatic relocation of absolute
paths when copying this layout to another machine or root.

## Reader compatibility, not automatic conversion

| Persisted record / reader | Behavior |
| --- | --- |
| Checkpoint schema 2, current schema-2 reader | Validate shape, seal/digest and sequence; matching versions alone do not establish safety or completion. |
| Checkpoint schema 1 or any other explicit integer version, current reader | `CHECKPOINT_VERSION_SKEW`, naming writer/reader versions; reconciliation is `FAIL_CLOSED`, not launchable. Original bytes remain intact. |
| Missing/noninteger version or malformed data | Not an explicit version-skew statement; ordinary shape/seal validation applies. Do not infer compatibility or invent a writer version. |
| Earlier reader against newer checkpoint | Release-specific refusal; code at 643c7ebe or earlier reports `CHECKPOINT_MALFORMED` for schema 2. Do not assume an old reader ignores it safely. |
| Envelopes, queue, decisions, heartbeat, capsule | Their own schema versions remain separate (currently 1); checkpoint schema 2 is not a blanket version bump. |

`tests/unit/test_program_checkpoint_version_skew.py` covers older/newer-version
refusal, preserved skewed bytes, current-version digest failures, and same-version
terminal positives. Current finite-behavior tests execute the current binary;
they do **not** prove arbitrary historical readers or binary rollback against
new state. `CONTINUATION-DELIVERY.md` is a historical implementation record,
not a current cross-version compatibility certificate.

No converter, automatic upgrade, downgrade, resealing, or in-place migration is
provided here. Retain the compatible reader environment and writer revision.
If compatibility cannot be established, keep dispatch paused and obtain a
separately reviewed migration/reconciliation decision. Changing `schema_version`
by hand is not migration; neither is recalculating a digest over changed data.

## Forward adoption: establish compatibility before admission

These are operator commands, not actions performed by this document:

```bash
atlas program status --governed-root <G> --program <P> --state-root <S>
atlas program queue --governed-root <G> --queue-root <Q> --action list
atlas program continuation --governed-root <G> --state-root <S> --queue-root <Q> \
    --action reconcile --worker-id <WORKER_ID>
atlas program capsule --governed-root <G> --state-root <S> --queue-root <Q> \
    --worker-id <WORKER_ID>
```

Use copies for checks with a proposed reader, preserving original bindings or
using a separately reviewed relocation procedure. Reconciliation is a read-only
decision lens, not execution or repair. An interrupted `ADAPTER_INVOKED` attempt,
uncertain effect, unreadable record or version skew must not be made eligible by
re-admission or clearing state. Admit only after current authority, compatibility
and outstanding decisions have been established. Do not replace an envelope to
silently widen old approval.

## Backward: operator-controlled code rollback

```bash
atlas program continuation --governed-root <G> --state-root <S> --action rollback
```

This prints guidance only: `performed: false`. It does not stop work, check
target-reader compatibility, snapshot state, reinstall code, or verify rollback.
It reports `preconditions_verified: false`, `automatic_migration: false`,
`checkpoint_reader_schema: 2` and `REQUIRES_COMPATIBLE_READER`. These fields
describe the procedure and current reader, not an observed compatibility check.

1. **Withhold new work** and record the approved rollback target, installed
   module provenance, checkout HEAD/TREE and reader versions.

   ```bash
   atlas program dispatcher --governed-root <G> --state-root <S> --action pause \
       --requested-by <OPERATOR_ID>
   atlas program dispatcher --governed-root <G> --state-root <S> --action status
   ```

2. **Drain and observe exit.** Allow work to settle; a submitted sentinel is
   not proof of exit. Confirm the recorded PID **and start identity** have
   exited, terminal reason is `OPERATOR_DRAIN`, and no owned workers remain.
   Unknown identity, timeout or an in-flight uncertain effect means stop the
   procedure, not kill/retry by PID alone.

   ```bash
   atlas program dispatcher --governed-root <G> --state-root <S> --action drain \
       --requested-by <OPERATOR_ID>
   atlas program dispatcher --governed-root <G> --state-root <S> --action status
   ```

3. **Preserve a byte-complete quiescent snapshot** of all queue-referenced state,
   checkpoints, envelopes, decisions, launch evidence, program bytes and binding
   context. Retain the original environment/revision. The commands above do not
   create that snapshot; use an approved backup procedure and verify its hashes.
4. **Check the target reader on preserved copies.** Require support for the
   actual schemas and no-replay evidence. An incompatible target blocks rollback;
   it is not a reason to erase/downgrade records. Retain a compatible reader or
   obtain a separate reviewed migration.
5. **Only after those checks**, repoint/install approved code into a noneditable
   pinned environment using the release procedure. Do not mutate a running shared
   checkout or reinterpret absolute state/workspace paths.
6. **Restart with pause retained under the same explicit boundary**, verify
   installed module provenance and expected HEAD/TREE, then inspect sequences,
   seals, terminal no-replay counts and uncertain quarantine. Resume only by a
   separate operator act when all gates hold. Rollback does not answer decisions,
   reopen COMPLETE entries, or grant authority.

## Evidence boundary

These are preparation and compatibility requirements, not a performed rollback,
service installation, failure restart, or reboot. Local-command fixture tests
and process-restart tests do not establish historical-binary compatibility or
host reboot recovery. See [operator commands](CONTINUATION-OPERATOR-COMMANDS.md)
and [installation preparation](../../../deploy/INSTALL-NOT-PERFORMED.md).
