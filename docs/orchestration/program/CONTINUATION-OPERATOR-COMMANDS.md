# Operator commands — durable continuation layer

Every command prints one JSON object. Two of them deliberately **do not act**:
`dispatcher --action restart` and `continuation --action rollback` print the
exact procedure instead of claiming a privilege this process does not hold.

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

## Restart — printed, not performed

```bash
atlas program dispatcher --state-root <S> --action restart
```

Returns `performed: false`, `reason: NOT_AUTHORIZED_FROM_HERE`, and the exact
commands. No service is installed by this package; see
`deploy/INSTALL-NOT-PERFORMED.md`.

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
