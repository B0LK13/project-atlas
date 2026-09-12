# Migration and rollback

`STATE_COMPATIBILITY = ADDITIVE_ONLY_NO_IN_PLACE_MIGRATION`

## There is no migration, and that is the design

This layer writes only **new files in new directories** under the program state
directory:

```
<state-root>/.atlas/orchestration/program/
    state.json          ← pre-existing, unchanged
    events.jsonl        ← pre-existing, appended to (new event names only)
    launches/           ← pre-existing, unchanged
    envelopes/          ← NEW
    checkpoints/        ← NEW
    decisions/          ← NEW
    dispatcher/         ← NEW
```

No existing file's schema changed. `ProgramStateRecord`, `AttemptRecord` and
`TaskRecord` are untouched, and `store.py` gained exactly one public function
(`write_json_atomic`) that wraps the atomic write it already performed.

So there is nothing to migrate forward and nothing to migrate back. A previous
revision reading this state directory ignores four directories it does not know
about and behaves exactly as it did before — which
`test_the_existing_finite_program_behaviour_is_unchanged` asserts directly, by
running a program the old way and checking that none of the four appear.

## Forward: adopting the layer on an existing state root

Nothing to run. The first `queue admit` creates `dispatcher/`; the first
envelope creates `envelopes/`. Programs mid-flight keep their `state.json` and
their in-flight launch records.

The one thing to check first, because it is the only way this can surprise you:

```bash
atlas program status --program <P> --state-root <S>
```

If an attempt is sitting at `ADAPTER_INVOKED` from a previous run, reconcile it
**before** admitting the program to the queue. The dispatcher runs the same
finite supervisor, which correctly refuses to redispatch it — you would simply
get a `RECONCILE_REQUIRED` quarantine and a decision record instead of work.

## Backward: rolling back the code

```bash
atlas program continuation --state-root <S> --action rollback
```

prints these steps with the preconditions checked. In full:

1. **Withhold new work.** `dispatcher --action pause`. Work already running
   finishes; pause is not cancel.
2. **Wait for quiet.** Poll `dispatcher --action status` until `state` is not
   `RUNNING_PROGRAM`.
3. **Stop cleanly.** `dispatcher --action drain`, then confirm
   `terminal_reason: OPERATOR_DRAIN` in the heartbeat. Draining rather than
   killing matters: a killed dispatcher leaves an attempt at `ADAPTER_INVOKED`,
   and the next start turns a rollback into a reconciliation.
4. **Repoint the pinned checkout** at the previous revision and reinstall
   non-editable into the pinned environment.
5. **Delete nothing.** In particular do not delete `checkpoints/`. A deleted
   terminal checkpoint is precisely how completed work becomes replayable
   again — it is the one action that can undo the no-replay guarantee.
6. **Restart and verify the revision.** The heartbeat's `revision_head` must be
   the revision you rolled back to. A restart that came back on different code
   is a fact to see here, not to discover later.

### What rollback does not undo

* **Decision records stay.** An operator's answer is evidence of a human act,
  and a code rollback did not un-decide it.
* **Queue `COMPLETE` entries stay complete.** That is the point.
* **Sealed checkpoints stay sealed.** A previous revision cannot read them and
  does not try to.

## Schema versioning

Every persisted model carries `schema_version: 1`. When a field is added, the
version rises and the reader must reject a version it does not know rather than
guessing at a partial document — the same fail-closed rule the rest of the
package uses. There is no version-1 reader that tolerates a version-2 file.
