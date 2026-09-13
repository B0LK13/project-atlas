# Operator commands — durable continuation layer

Every command prints one JSON object. `continuation --action rollback`
deliberately **does not act**: it prints the exact procedure instead of claiming
a privilege this process does not hold. `dispatcher --action restart` takes a
witness first and, by default, also only prints; it acts only in `--mode
supervised`, with a command the operator declared, and it proves what it did
with `--action restart-verify` (see Restart below).

`<S>` = state root · `<Q>` = queue root · `<P>` = approved program file.

## Admitting work — the only way work ever enters

```bash
atlas program queue --queue-root <Q> --state-root <S> --action admit \
    --program <P> --admitted-by "$USER" --reference "<where approval is written>"
atlas program queue --queue-root <Q> --action list
atlas program queue --queue-root <Q> --action withdraw --program-id <ID> --note "why"
```

Admission pins the program file's sha256. `list` reports `pin_check`:
`MATCHES_ADMITTED_BYTES`, or a refusal. **An entry whose file changed is not
run** — the approval was for the bytes, not for the path. Admitting also
requests a wake, so a sleeping dispatcher picks it up without a full tick.

## Running the dispatcher

```bash
# foreground, bounded (what you run first)
atlas program dispatcher --state-root <S> --queue-root <Q> --action run \
    --tick-seconds 5 --max-seconds 300

# detached, surviving terminal closure, no service needed
setsid nohup atlas program dispatcher --state-root <S> --queue-root <Q> \
    --action run >> <S>/dispatcher.log 2>&1 < /dev/null &
```

## Status, health and events

```bash
atlas program dispatcher --state-root <S> --action status
atlas program events --program <P> --state-root <S>
```

`alive` is three-valued and must be read as such:

| value | means |
| --- | --- |
| `true` | the recorded pid is running **under the recorded start identity** |
| `false` | it demonstrably is not — dead, or a stranger on a reused pid |
| `null` | nothing could be compared. **This is not a yes.** |

## Pause, resume, drain, stop

```bash
atlas program dispatcher --state-root <S> --action pause  --requested-by "$USER"
atlas program dispatcher --state-root <S> --action resume
atlas program dispatcher --state-root <S> --action drain  --requested-by "$USER"
atlas program dispatcher --state-root <S> --action stop   --requested-by "$USER"
atlas program dispatcher --state-root <S> --action wake
```

* **pause** withholds *new* dispatch. A program already running is left to
  finish — *pause is not cancel*. It **survives a restart**, deliberately:
  clearing it would resume work a person withheld, at exactly the moment
  nobody is watching.
* **drain** finishes the current program, starts nothing, then exits.
* **stop** ends at the next tick boundary; it does not interrupt a running
  program.

## Restart — witnessed, then delegated or supervised, then verified

```bash
# default: take a witness, print the operator commands, stop and start nothing
atlas program dispatcher --state-root <S> --queue-root <Q> --action restart

# only with an operator-written restart_command (see below)
atlas program dispatcher --state-root <S> --queue-root <Q> --action restart \
    --mode supervised --wait-seconds 30

# judge a restart (a hand restart included) against the witness
atlas program dispatcher --state-root <S> --queue-root <Q> --action restart-verify
```

Every mode first takes a **witness** and writes it atomically to
`<S>/.atlas/orchestration/program/dispatcher/restart-witness.json`: the outgoing
dispatcher's session id, pid and start identity, revision head and tree, both
pause flags, the in-flight program, queue status, terminal and
`RECONCILE_REQUIRED` task ids, launch counts, and `witnessed_at`.

Refusals (non-zero exit, nothing stopped, nothing written):

| code | when |
| --- | --- |
| `RESTART_IDENTITY_UNVERIFIABLE` | `dispatcher_status()["alive"]` is `None` — no heartbeat, or a pid whose start identity cannot be compared. `alive: null` is not a yes. |
| `RESTART_COMMAND_NOT_DECLARED` | `--mode supervised` and no `restart_command` is declared. Nothing is guessed in its place. Checked before any process is looked at. |
| `RESTART_COMMAND_INVALID` | the declaration file exists but does not hold a usable command |
| `RESTART_WAIT_SECONDS_OUT_OF_BOUNDS` | `--wait-seconds` outside (0, 600] (exit 2) |

* **delegate** (default) keeps the old contract — `performed: false`,
  `reason: NOT_AUTHORIZED_FROM_HERE`, `operator_commands` — and adds the witness
  and the `restart-verify` command.
* **supervised** runs only a command the operator wrote into
  `<S>/.atlas/orchestration/program/dispatcher/restart-command.json` as
  `{"restart_command": ["argv0", "arg", ...]}` (or one string, split into words
  and run **without a shell**). This package never writes that file. Stop is the
  existing drain, followed by a bounded wait for the recorded pid to leave under
  its recorded start identity; no signal is ever sent. If it does not leave in
  time the restart refuses with `RESTART_STOP_NOT_OBSERVED` and starts nothing.
  Then the declared command is started exactly, and the verdict is taken.

The verdict is four independent codes, each `PASS`, `FAIL` or `UNVERIFIABLE`,
with no aggregate field; the exit status is 0 only when all four are `PASS`:

| criterion | PASS means |
| --- | --- |
| `service_and_candidate` | a new process (session id, and pid + start identity) published, `alive` is `True`, and revision head/tree are byte-identical to the witness |
| `state_recovery` | every in-flight checkpoint is still readable, its sequence did not go back, its content is unchanged at an unchanged sequence, its step did not regress, and reconciliation does not start it from nothing |
| `pause_and_uncertain` | a witnessed pause is still in place with zero launches by the new dispatcher, and every witnessed `RECONCILE_REQUIRED` task is still `RECONCILE_REQUIRED` and not launchable |
| `no_double_execution` | for every task with a terminal checkpoint, launches in `state.json` after minus before is exactly 0, and reconciliation keeps it unlaunchable |

A missing or torn witness makes all four `UNVERIFIABLE`, never `PASS`. The
verdict is written to `restart-verdict.json` beside the witness. It is a
point-in-time judgement: re-run `restart-verify` later to judge again. A restart
is not a reboot and proves nothing about power loss. No service is installed by
this package; see `deploy/INSTALL-NOT-PERFORMED.md`.

## Version skew in durable checkpoints

A checkpoint records the `schema_version` of the code that wrote it (currently
`2`). A checkpoint written at any other version is refused **before** it is
validated or its digest is checked, with `CHECKPOINT_VERSION_SKEW`, naming
`writer_schema_version=` and `reader_schema_version=`, in both directions
(an older or a newer writer). Its reconcile disposition is `FAIL_CLOSED`, not
launchable, and the record is left untouched.

This is **not** a corruption report: the record may be entirely intact. Finish
or revert the upgrade, or reconcile the task explicitly; do not wipe the state
root because of it. A record edited at the current version is still refused as
`CHECKPOINT_DIGEST_MISMATCH`. Code at 643c7ebe or earlier reading a version-2
checkpoint still reports `CHECKPOINT_MALFORMED`; that older code is not changed
by this.

## Continuation: capsule, reconcile, rollback

```bash
# what a replacement session reads instead of a transcript
atlas program capsule --state-root <S> --queue-root <Q> --worker-id <WORKER_ID>

# what may safely happen next for every task with an envelope
atlas program continuation --state-root <S> --action reconcile --worker-id <WORKER_ID>

# the exact rollback procedure, verified preconditions, performed by a human
atlas program continuation --state-root <S> --action rollback
```

Dispositions and what each permits:

| disposition | launchable | meaning |
| --- | --- | --- |
| `START_FRESH` | yes | never run |
| `RESTART_FROM_TOP` | yes | replay-safe by declaration |
| `RESUME_AT_NEXT_STEP` | yes | continue at `resume_step` — **not** the top |
| `WORKER_STILL_RUNNING` | no | leave it alone |
| `ALREADY_COMPLETE` | no | **never replayed** |
| `RECONCILE_REQUIRED` | no | quarantined; an operator establishes what happened |
| `HUMAN_DECISION_REQUIRED` | no | a person decides first |
| `LEASE_HELD_ELSEWHERE` | no | someone else holds it and it has not expired |
| `FAIL_CLOSED` | no | durable state is unusable. **Nothing repairs it.** |

## Envelopes and checkpoints

```bash
atlas program envelope   --state-root <S> --action list
atlas program envelope   --state-root <S> --action show --task <TASK_ID>
atlas program checkpoint --state-root <S> --action list
atlas program checkpoint --state-root <S> --action show --task <TASK_ID>
```

## The decision queue

```bash
atlas program decisions --state-root <S> --action list [--status OPEN]
atlas program decisions --state-root <S> --action answer \
    --decision-id <ID> --answered-by "$USER" --answer "<what you decided>"
atlas program decisions --state-root <S> --action withdraw \
    --decision-id <ID> --answer "<why it is no longer live>"
```

A blocker is recorded **once**. A recurrence bumps `seen_count` — it does not
create a second request and does not re-notify. An answered decision cannot be
re-answered: a second answer would erase who decided what.

**Recording an answer grants nothing.** It unblocks selection. Owner gates,
merge authorization and model-backed dispatch are unchanged by it.
