# Limitations and unresolved risks

Written before independent verification, deliberately. Each item is something a
verifier should be able to confirm is stated here rather than discover.

## Not delivered, and why

| claim the goal asks for | status | why |
| --- | --- | --- |
| `SYSTEM_SERVICE=INSTALLED_ENABLED_REBOOT_VERIFIED` | **NOT_DELIVERED** | needs root, a new system account, and a reboot of a shared host. The directive in force says "Do not install a system service"; standing constraints say sudo and machine-wide service installation are not authorized. The reviewed template and the exact operator procedure are in `deploy/`. |
| reboot recovery | `NOT_VERIFIED` | only a real reboot proves it. Generated configuration is not evidence. |
| `VPS_PORTABILITY=VERIFIED` | **argued, not verified** | the layer uses no `inotify`, no D-Bus, no machine id and no path outside the state root — but no VPS was provisioned, and an argument from absent host dependencies is not a migration that was performed. |
| `INDEPENDENT_VERDICT=PASS` | `PENDING` | I implemented this. I am disqualified from verifying it. |

## Stated limits of what was proven

**Fixture adapters only.** `FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY`. The
Claude Code and Codex adapters still load and validate; neither was launched.
Nothing here establishes that a real runtime's cancellation, rate-limiting or
unparseable result flows through this layer the way the fixture's does.

**"Efficient waiting" is bounded polling, not a blocking primitive.** One
`stat` per wake quantum (default 0.5 s) and one queue read per tick (default
5 s). It is not `inotify` and the module says so. The test measures CPU over a
real idle hold rather than trusting the description — but a machine under heavy
load could still see a longer wake latency than the quantum suggests.

**The zero-network proof covers this interpreter only.** The socket ban in
`test_the_whole_layer_makes_zero_model_calls_and_opens_no_socket` applies to
the process running the dispatcher, the reconciler and the capsule. It does not
instrument the fixture child process; instead the test asserts the child's argv
is the local fixture worker, which opens nothing. A different adapter would
need its own proof.

**Concurrency is not exercised by this layer's tests.** The dispatcher runs one
program at a time and the supervisor's own concurrency is covered by the
pre-existing suite. Two dispatchers against one state root are not tested and
not supported: nothing in this layer takes a cross-dispatcher singleton lock.

**Clock trust.** Deadlines and lease expiry are compared against the local
clock. A host whose clock jumps backwards can make an expired lease look live
and a passed deadline look future. There is no monotonic durable clock here,
and the registry host in this program is already known to run ~59 minutes fast.

**Python 3.14 is outside the supported matrix, and it is not clean.** Built
against Python 3.12 (`pyproject.toml` targets 3.12; CI runs 3.12 and 3.13). A
3.14.4 environment fails five PRE-EXISTING tests in
`test_discovery_error_policy.py` and `test_linux_filesystem_portability.py`.
Established as pre-existing by a matched control: the same five fail on the
pristine base commit `250eb1cb` in the same environment with every change of
mine stashed, and all five pass on 3.12 with the changes applied. It is a real
finding about the repository on 3.14, and it is not this layer's.

**Windows is untested for this layer.** The code avoids POSIX-only calls and
reuses the package's existing cross-platform identity helpers, but every test
here ran on Linux. `resource.getrusage` in the idle-waiting test is POSIX-only
and that test would need a different oracle on Windows.

## Corrected after independent verification

Two defects found by an independent verifier (Agent 9,
`session_018dYPZn6KzN79PQhZWS1JS9`) running this as an operator rather than as
a test suite. Both are fixed and both now have a test that a mutation kills.

**F1 — the state root split.** The dispatcher publishes its heartbeat under its
own root (the `--state-root` flag) while each admitted program keeps its task
records under the root in its queue entry. Those differ by design whenever one
dispatcher serves several programs. `build_capsule` read only the dispatcher's
root, so a healthy, completed program produced a capsule saying *"no task
envelopes recorded under this state root"* — and a replacement session reading
that would reasonably conclude there was nothing to resume. This is the same
silent-emptiness failure the layer is supposed to prevent, in the one surface
that matters most. The capsule now scans every admitted program's state root,
records which root each task came from, and states the split explicitly. An
empty capsule now names the roots it actually looked in.

**F2 — a corrupt queue failed closed but not distinguishably.** `queue --action
list` reported `QUEUE_UNREADABLE` correctly, but `dispatcher --action run`
returned exit 0, zero launches and no error, so an operator could not tell an
unreadable manifest from an empty queue. The in-process test asserted the tick's
state and notes, which were correct and *invisible* — the CLI payload carried
neither. Now three independent signals separate them: `queue_status`
`UNREADABLE` vs `READABLE`, a `QUEUE_UNREADABLE` code with the path and parse
error, and process exit status 1 vs 0. The heartbeat carries it too, for a
reader who arrives later.

The lesson recorded, because it recurs: a test can assert a true thing about a
surface the operator never sees.

**F3 — a schema-invalid document escaped as a traceback.** Found by the same
verifier while building a control for F2: a queue file that parsed as JSON but
had `entries` as a list raised a raw `pydantic_core.ValidationError`. It failed
loudly, which beats failing silently, but a traceback names no stable code a
script can branch on and does not say which file is at fault.

It was never one call site. **Eight** readers in this layer called
`model_validate` and only the checkpoint one wrapped it, so the same hole
existed for envelopes, decisions and the heartbeat. All of them now funnel
through `read_durable`, which raises the reader's own error type with a stable
code and the offending path. A fix applied only to the reported file would have
passed a test that only checked the queue, so the regression test walks every
reader.

**F2, as the verifier narrowed it.** They withdrew their own "an operator cannot
tell them apart" as too strong: the run path *did* differ, by reporting
`TICK_BUDGET_REACHED` where an empty queue reports `QUEUE_DRAINED`. The accurate
finding is that it reported a **benign timeout for an unreadable authoritative
input** — "ran out of ticks" is equally what a slow or busy queue produces, it
names no file, and with five ticks it burned all five in silence. There is now a
`QUEUE_UNREADABLE` terminal reason and the run stops on the first tick: a
dispatcher whose only source of work is unreadable has nothing it could discover
by waiting. Damaged bytes (`QUEUE_UNREADABLE`) and a valid document of the wrong
schema (`QUEUE_SCHEMA_INVALID`) are kept apart, because they are different
operator problems — one is a damaged file, the other a version mismatch.

The authoritative input is never rewritten. A run that "repaired" the queue
would destroy the evidence of what was wrong with it, and the regression test
asserts the file is byte-identical afterwards.

## Coverage gaps closed in the release-handoff round

Mapping the fourteen proofs onto the plan showed three properties tested only in
**halves**, where the halves do not compose:

* **pause** survived a restart in a test with an *empty queue* (so it could not
  show withholding) and withheld work in a test that never restarted. A pause
  that survived as a file while ceasing to block would have passed both. Now
  tested together, with eligibility proven by making the same restarted
  dispatcher launch the instant pause is cleared — so `ROLE_CONTENTION` and
  `RECONCILE_REQUIRED` cannot be the hidden cause.
* **cleanup** was proven against a helper the test file spawned itself, not
  against the dispatcher → supervisor → adapter route where the pids actually
  come from. Now proven on that route, from the records the adapter wrote.
* **the dispatcher feeding the layer** was only ever shown with tasks that all
  reached `CERTIFIED`, so every disposition was `ALREADY_COMPLETE`. Now shown
  with a task whose acceptance fails and a dependant that never becomes
  eligible.

### Still open: G4

Plan §2 lists *changed files*, *commands and observed results* and *artifacts
and hashes* as checkpoint contents. The model carries all three and the schema
validates them, but the dispatcher's **boundary projection leaves them empty**,
because it writes at program boundaries and does not observe a worker's diff. A
task that writes its own step checkpoints can populate them. A capsule from a
dispatcher-run program therefore shows `artifacts: []` — honest, but less than
the plan asks for.

## Open risks carried in from the program

* **R-12 open.** Cleanup by process identity in a shared session. This layer
  never kills by name, pattern or working directory, and its own tests assert
  that property against their source — but R-12 is not closed by that.
* **R-13 open.**
* **`MODEL_BACKED_DISPATCH=DISABLED`** until R-12 closes *and* this layer has
  independent verification.

## Things a verifier should specifically try to break

1. Delete a terminal checkpoint and check whether completed work becomes
   replayable. It should — that is the documented single point of failure for
   the no-replay guarantee, and the rollback procedure says not to do it.
2. Run two dispatchers against one state root. Nothing stops you; nothing
   claims it is safe.
3. Set the host clock backwards and re-run the stale-lease test.
4. Hand the capsule a state root with 500 envelopes and check that every
   truncation is announced.
5. ~~Corrupt `approved-work-queue.json`~~ — raised here, then defended:
   `test_a_corrupt_queue_is_reported_and_never_looks_like_an_empty_one` asserts
   the dispatcher reports `WAITING_ON_WORK`, not `IDLE_EMPTY_QUEUE`. Try to
   find the version of this that is still collapsed somewhere else.
