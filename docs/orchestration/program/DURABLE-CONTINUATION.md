# Durable continuation — architecture and state transitions

`AS-ORCH-DURABLE-CONTINUATION-001` / directive
`ATLAS-DURABLE-AUTONOMOUS-CONTINUATION-001`.

**A conversational session is disposable. Durable task state is authoritative.**

This layer sits *above* `supervisor.py`, which stays finite by design: it
executes one approved program until `PROGRAM_COMPLETE` and exits. What was
missing was everything that has to survive that exit — and the exit of the
terminal, the worker session, the dispatcher process and the host.

```
    operator                                                 durable files
    ────────                                                 ─────────────
    admit program  ──► approved-work queue  (pinned by sha256)
                            │
                            ▼
                    ResidentDispatcher          dispatcher/heartbeat.json
                    (model-free, resident)      dispatcher/dispatcher.pause
                            │                   dispatcher/dispatcher.wake
                            │ one program at a time
                            ▼
                    ProgramSupervisor  ──────►  state.json, events.jsonl
                    (finite; exits on                launches/*.json
                     PROGRAM_COMPLETE)
                            │
                            ▼
                    task execution      ──────►  envelopes/*.envelope.json
                                                 checkpoints/*.checkpoint.json
                                                 decisions/*.decision.json
                            │
                            ▼
    replacement session ◄── continuation capsule (generated, bounded)
```

Nothing in the right-hand column is authority. All of it is evidence. A worker
can write none of it.

## The four identities

Conflating any two is the defect class this layer is built against.

| identity | lifetime | what it names | what breaks when it is conflated |
| --- | --- | --- | --- |
| `task_id` | immutable | the unit of work in the approved program | no-replay keys on it; a task named after an execution can be run twice |
| `worker_id` | stable | the principal doing the work | authority attached to a session expires when a terminal closes |
| `session_id` | one process | the process lifetime | a lease held by a session is a lease lost to a window close |
| `attempt_id` | one execution | one dispatch of one task | the unit a replay decision is made about |

`ExecutionIdentity` **refuses to construct** when `worker_id == session_id` or
`task_id == attempt_id`. The first is the dangerous one: it reads as harmless
because both say "who is doing it", and it is how a stable principal quietly
acquires a lifetime.

## The task envelope

Persisted before dispatch; re-read on every restart. It carries objective,
dependencies, required capabilities, the exact `candidate_head`/`candidate_tree`
the authority was granted against, allowed and forbidden paths and actions,
acceptance checks, budgets, a deadline, the checkpoint policy, fallback tasks,
and the declared replay class — plus the approval provenance, which is recorded
and **never treated as a credential**.

`validate_envelope_for_dispatch` is called **immediately before every
dispatch**, never once at start-up, because each of these becomes true *during*
a long run:

| refusal code | what became true |
| --- | --- |
| `ENVELOPE_PROGRAM_MISMATCH` | the envelope names another program |
| `ENVELOPE_TASK_NOT_APPROVED` | the task is not in the approved program |
| `ENVELOPE_FALLBACK_NOT_APPROVED` | a fallback is not approved work |
| `ENVELOPE_HEAD_MOVED` / `ENVELOPE_TREE_MOVED` | the worktree moved off the approved candidate |
| `ENVELOPE_DEADLINE_PASSED` | time passed — the condition a start-up check can never catch |
| `ENVELOPE_BUDGET_EXHAUSTED` | attempts, launches, wall clock, model calls or cost ran out |

Construction-time refusals (`ENVELOPE_CONTRADICTORY_ACTIONS`,
`ENVELOPE_CONTRADICTORY_PATHS`, `REPLAY_CLASS_NOT_DECLARABLE`,
`ENVELOPE_NO_STEPS`, `ENVELOPE_NO_CHECKPOINTS`,
`ENVELOPE_MODEL_CALLS_FORBIDDEN`) keep their own exception type rather than
being wrapped in a pydantic `ValidationError` — the machine code is the
interface, and a caller keys on `ENVELOPE_CONTRADICTORY_PATHS`, not on a
sentence that may be reworded.

## Replay classes: declared vs derived

Six classes. **Four may be declared by a task. Two may only ever be derived.**

| class | declarable | meaning | restart behaviour |
| --- | --- | --- | --- |
| `READ_ONLY_REPLAYABLE` | yes | writes nothing but its own evidence | restart from the top |
| `IDEMPOTENT_MUTATION` | yes | re-applying is indistinguishable from applying once | restart from the top |
| `CHECKPOINT_RESUMABLE` | yes | non-idempotent, but stepwise and checkpointed | resume at the step after the last recorded complete — **never the top** |
| `UNCERTAIN_EXTERNAL_EFFECT` | yes | can act outside this machine's observation | never automatically repeated |
| `COMPLETED` | **no** | finished and sealed | never replayed |
| `HUMAN_DECISION_REQUIRED` | **no** | a person must decide first | nothing automatic |

A task that could declare itself `COMPLETED` is a task that can skip its own
work; one that could declare `HUMAN_DECISION_REQUIRED` is one that can summon
an operator. `declarable()` is enforced by the validator.

## Continuation checkpoints

Atomic (create → fsync → rename), sealed with a sha256 over their own content,
and carrying a **monotonic per-task `sequence`**.

Contents: the four identities, the envelope digest, last completed step and the
concrete next action, worktree path with git HEAD/TREE/branch/dirty, changed
files, commands with their observed results, the lease snapshot, the deadline,
the process pid **paired with its start identity**, artifacts with hashes,
consumed budget, blockers, uncertainty, and external-effect receipts.

Three refusals, and none of them repairs anything:

* `CHECKPOINT_DIGEST_MISMATCH` — truncated or edited after it was written.
* `CHECKPOINT_UNSEALED` — no digest, so it cannot be told apart from a truncated one.
* `CHECKPOINT_SEQUENCE_REGRESSION` — two writers disagree about one task. The
  **older record is left intact** for a human to look at.

A pid without a start identity is refused at construction
(`CHECKPOINT_PID_WITHOUT_IDENTITY`): a pid alone cannot be told apart from a
reused one, which this program has had to fix twice already.

## Restart reconciliation — the order is the specification

`reconcile_task` is pure given its inputs, so the whole decision table is in one
place and its ordering is visible rather than spread across callers.

1. **Envelope digest mismatch → `FAIL_CLOSED`.** The authority changed
   mid-flight; continuing would execute the remainder under terms nobody
   approved.
2. **`COMPLETED` → `ALREADY_COMPLETE`.** First, before liveness, leases and
   budgets, because every branch below could otherwise reach a launch.
3. **Terminal `HUMAN_DECISION_REQUIRED` → `HUMAN_DECISION_REQUIRED`.**
4. **Holder `ALIVE` → `WORKER_STILL_RUNNING` / `LEASE_HELD_ELSEWHERE`.** A live
   holder outranks everything below it.
5. **Any unconfirmed external-effect receipt, or recorded uncertainty, or a
   declared `UNCERTAIN_EXTERNAL_EFFECT` that did not reach a terminal
   checkpoint → `RECONCILE_REQUIRED`.** Checked *before* the resume branches: a
   `CHECKPOINT_RESUMABLE` task that emitted an unconfirmed effect at its last
   step is exactly the case where "resume at the next step" would skip a
   reconciliation. **A missing receipt is not proof of a missing effect.**
6. **Unexpired lease held by someone else → `LEASE_HELD_ELSEWHERE`.**
   Reacquisition needs *expiry* **and** an *identity check*, never one of them.
7. **Budget spent → `HUMAN_DECISION_REQUIRED`.** Raising a budget is an
   operator decision, not a retry.
8. **`CHECKPOINT_RESUMABLE` → `RESUME_AT_NEXT_STEP`.** Every step complete but
   no terminal seal is `RECONCILE_REQUIRED`, not "finished": the seal is what
   makes completion a fact, and inventing it would be this layer certifying its
   own predecessor.
9. **`READ_ONLY_REPLAYABLE` / `IDEMPOTENT_MUTATION` → `RESTART_FROM_TOP`.**

Only `START_FRESH`, `RESTART_FROM_TOP` and `RESUME_AT_NEXT_STEP` are in
`LAUNCHABLE`, and that set is explicit so a new `Disposition` member cannot
become launchable merely by existing.

### Three-valued liveness, again

`holder_liveness` reuses `recovery.Liveness` rather than returning a boolean.
`GONE` (demonstrably not ours) and `UNKNOWN` (nothing recorded to check) are
different facts, and a caller will turn the second into a launch if they are
collapsed. `ALIVE` requires the live start identity to **match** the recorded
one; a live pid under a different identity is `GONE` — our process exited and
the number was reused.

## The resident dispatcher

Model-free. Three properties, each a refusal:

**It does not spin.** Idle time is spent asleep in bounded quanta: one `stat`
of the wake sentinel per quantum (default 0.5 s), one queue read per tick
(default 5 s). It is **not** an `inotify` subscription and does not claim to
be — a portable blocking primitive that works on Linux, macOS and Windows and
survives a network filesystem does not exist, and a Linux-only wake would make
this untestable on platforms the package already supports. The honest measure
is CPU consumed while idle, and the acceptance test measures it directly
(`cpu < wall * 0.25` over a real 3-second hold).

**It does not restart completed programs.** A queue entry that reached
`COMPLETE` is terminal; `update_entry` refuses to return it to a runnable
status (`QUEUE_COMPLETE_IS_TERMINAL`).

**It does not invent work.** One source of tasks — programs an operator
admitted — and no discovery path. Empty queue means wait, not propose.

Published every tick, atomically: session id, pid **and** process start
identity, hostname, revision HEAD/TREE of the running checkout, state, pause
state and who requested it, current program, last program stop reason, terminal
reason, programs started, launches, and `model_calls: 0`.

### Signals

| file | effect | cleared at start-up? |
| --- | --- | --- |
| `dispatcher.wake` | shorten the current sleep | yes |
| `dispatcher.pause` | withhold **new** dispatch; a running program finishes | **no** |
| `dispatcher.stop` | stop at the next tick boundary | yes |
| `dispatcher.drain` | finish the current program, start nothing, exit | yes |

Pause deliberately survives a restart. Clearing it would resume work a person
withheld, and the restart is exactly when nobody is watching.

## When a task blocks

Three acts and a refusal, in this order (`blocked_work.handle_blocked_task`):

1. **One durable decision record.** A recurrence bumps `seen_count`; it never
   creates a second request and never re-notifies.
2. **Release the lease safely** — through the existing projection, with the same
   foreign-worker and stale-base checks any other release gets. The lease is
   reconstructed from the projected row, never accepted from a caller.
3. **Select an eligible fallback** — named in this envelope (so it came from the
   approved program), with its own recorded envelope, and without an open
   decision of its own (so yielding does not immediately produce a second
   question).
4. **Do not ask again.**

Categories that are always an operator's: `PERMISSION`, `BUDGET_INCREASE`,
`SCOPE_EXPANSION`, `MERGE`, `PUSH`, `RELEASE`, `CREDENTIAL`, `ACL_OR_ACCOUNT`,
`SERVICE_CHANGE`, `UNCERTAIN_EXTERNAL_EFFECT`. The enum is closed on purpose: a
blocker that fits none of them is usually a bug or a missing capability, and a
catch-all would fill the queue with things nobody can act on.

Recording an answer is an **evidence act**. It unblocks selection; it does not
widen what a task may do. Owner gates are unchanged by it. An answered decision
cannot be re-answered — a second answer overwriting the first would erase who
decided what.

## The continuation capsule

Generated from durable files: the approved program, the envelopes, the sealed
checkpoints, the reconciliation verdicts, the open decisions and the heartbeat.
It reads **no transcript** and takes no argument a previous session could have
written in prose.

Bounded at `CAPSULE_MAX_BYTES` (16 KiB). **Truncation is always announced**, in
the place the content would have been — a reader cannot otherwise tell a short
list from a truncated one. A task whose state cannot be read still appears, as
`FAIL_CLOSED`; omitting it would make the task list a statement that the task
does not exist.

`CAPSULE_GENERATED != AUTHORITY_GRANTED`. A session that reads a capsule still
passes `validate_envelope_for_dispatch`, which reads the envelope on disk.

## Truth boundaries

```
PROGRAM_APPROVAL      != MERGE_AUTHORIZATION
CHECKPOINT_PRESENT    != WORK_COMPLETE
CAPSULE_GENERATED     != AUTHORITY_GRANTED
DECLARED_REPLAY_CLASS != OBSERVED_OUTCOME
RESUMABLE             != SAFE_TO_REPEAT
FIXTURE_RUN           != REAL_RUNTIME_COMPATIBILITY
```
