# Delivery record — AS-ORCH-DURABLE-CONTINUATION-001

Directive `ATLAS-DURABLE-AUTONOMOUS-CONTINUATION-001`, under goal
`ATLAS-PERSISTENT-AUTONOMOUS-SUPERVISOR-001`.

**I implemented this. I am not its verifier.** Nothing below is an independent
verdict, and `INDEPENDENT_VERDICT` stays `PENDING` until somebody who did not
write this reproduces it from the exact commit.

## Base and scope

```
BASE_HEAD  250eb1cb9c088712c1dde33554845e51c4b45e18   (candidate 010c)
BASE_TREE  d5100d311db84dd22991c823dc0699302496c3f7
WORKTREE   /home/gebruiker/atlas-continuation-001  (dedicated, clean at base)
PYTHON     3.12.14  (pyproject targets 3.12; CI runs 3.12 and 3.13)
```

Base chosen because the directive names it as `DEPLOYED_HEAD` and because it is
the head with validated 010c behaviour. 010e (the codex false-version fix) is a
descendant and was deliberately **not** used: it is local-only and has had no
independent verification, and building on unverified work would put this layer's
evidence behind someone else's open question.

### Surfaces touched

Three tracked files changed, 52 insertions, 2 deletions:

| file | change | why it was unavoidable |
| --- | --- | --- |
| `store.py` | +1 public function (`write_json_atomic`) | the new layer needs exactly the atomic write this module already performed; a second implementation is a second chance to get the fsync wrong |
| `cli.py` | import + one registration call + handler lookup | wiring, no behaviour change |
| `README.md` | one section pointing at the new docs | discoverability |

`supervisor.py` (3095 lines) is **untouched**. So are `models.py`,
`recovery.py`, `control.py`, `service.py` and every adapter.

Ten new modules (4,449 lines), two new test files (2,144 lines), six new JSON
schemas, five new documents, one uninstalled service template.

## The fourteen mandatory proofs

All in `tests/unit/test_program_durable_continuation.py`. Tests 1–4 and 11
spawn a real interpreter, wait for it to seal a checkpoint, and `SIGKILL` it by
pid; 1–3 then reconcile through the CLI **in a fresh process**, so "does not
depend on prior chat history" holds because there is no prior process at all.

| # | requirement | result | test |
| --- | --- | --- | --- |
| 1 | killed mid read-only task → replacement session resumes | PASS | `..._read_only_task_is_resumed_safely_by_a_replacement_session` |
| 2 | killed after checkpointed mutation → next step, not the top | PASS | `..._checkpointed_mutation_resumes_at_the_next_step` |
| 3 | crash during uncertain mutation → no replay, reconcile | PASS | `..._uncertain_mutation_is_never_replayed` (+ mutation twin) |
| 4 | completed task survives two restarts, zero launches | PASS | three tests: queue-level, reconciliation-level, and a mutation twin |
| 5 | blocked task releases its lease, fallback runs | PASS | `..._releases_its_lease_and_an_eligible_fallback_is_selected` (+2) |
| 6 | empty queue → efficient waiting, not exit or spin | PASS | measured as **CPU over a real 3 s idle hold**, not a tick count |
| 7 | new approved work wakes the dispatcher, launches once | PASS | `..._wakes_the_dispatcher_and_launches_exactly_once` |
| 8 | pause blocks dispatch, names in-flight work, resume continues | PASS | `..._blocks_new_dispatch_reports_in_flight_work_and_resume_continues` |
| 9 | suspended / mismatched / duplicate-role workers launch nothing | PASS | four tests incl. identity conflation |
| 10 | corrupt checkpoint and stale lease fail closed | PASS | seven tests |
| 11 | cleanup by pid **plus** start identity, no leaks | PASS | `..._leaks_no_test_processes` + a source-read R-12 guard |
| 12 | budgets and authority rechecked before every dispatch | PASS | four tests incl. the byte-pin on an admitted program |
| 13 | existing finite-program behaviour unchanged | PASS | two tests, incl. "none of the four new directories appear" |
| 14 | zero model calls, zero network | PASS | `socket.socket` banned during the run; argv asserted to be the fixture |

Plus: schema-drift tests, capsule boundedness, the operator-command surface,
and the projection integration.

## Mutation testing — every guard shown to be load-bearing

A passing test proves nothing until removing what it defends makes it fail.

| # | protection removed | test killed |
| --- | --- | --- |
| M1 | `COMPLETED` early return in `reconcile_task` | **initially survived — a real gap, see below** |
| M2 | unconfirmed-receipt quarantine | 2 tests |
| M3 | `QUEUE_COMPLETE_IS_TERMINAL` | 1 test |
| M4 | checkpoint self-digest verification | 1 test |
| M5 | dispatcher pause sentinel | 1 test |
| M6 | admitted-bytes pin check | 1 test |
| M7 | envelope materialisation idempotence | 1 test |
| M8 | projection's unreadable-checkpoint refusal | **survives alone; see below** |

**M1 found a real hole.** Removing the no-replay guard in `reconcile_task`
broke nothing, because every existing proof of no-replay went through the
queue's `COMPLETE` status instead. Two independent mechanisms defend the
headline property and only one was defended — a refactor could have deleted the
other in silence. Fixed by
`test_a_terminal_completed_checkpoint_is_never_replayed_by_reconciliation`,
after which M1 kills it.

**M8 is honest redundancy, measured.** The projection's own refusal to
overwrite an unreadable checkpoint can be removed with no test failing, because
`persist_checkpoint`'s sequence check catches it anyway. Removing **both** lets
the projection clobber a tampered file. Kept, and the code comment now says
which of the two is actually load-bearing today instead of implying it is the
nearer one.

## An integration gap found by use, not by reasoning

Every mechanism passed its own test while a real dispatcher run produced a
capsule saying *"no task envelopes recorded under this state root"*. The layer
was correct and nothing fed it. `continuation_projection.py` closes it —
envelopes materialised before the program runs, checkpoints projected from
durable state after it stops — and
`test_a_dispatcher_run_leaves_a_capsule_a_replacement_session_can_use` is the
test that would have caught it.

The limit is stated rather than glossed: these are **program-boundary**
checkpoints. They answer "may this run again?"; they do not answer "which of
its five steps landed?". A task wanting step-level resume declares steps in its
envelope and writes its own checkpoints — same `persist_checkpoint`, and
reconciliation treats both identically.

## What is NOT delivered

| goal criterion | status |
| --- | --- |
| `SYSTEM_SERVICE=INSTALLED_ENABLED_REBOOT_VERIFIED` | **BLOCKED_ON_OPERATOR** — needs root, a new system account and a host reboot. The directive in force says "Do not install a system service"; standing constraints exclude sudo and machine-wide service installation. Reviewed template + exact procedure in `deploy/`. |
| reboot recovery / failure restart of the pinned revision | `NOT_VERIFIED` — only a real reboot and a real service prove these |
| `VPS_PORTABILITY=VERIFIED` | **argued, not verified** — no VPS was provisioned |
| `INDEPENDENT_VERDICT=PASS` | `PENDING` |
| `MODEL_BACKED_DISPATCH` | `DISABLED_PENDING_R12_AND_IV` |

## Findings recorded along the way

**Python 3.14 is not clean for this repository, and it is not this layer's
doing.** A 3.14.4 environment fails five pre-existing tests in
`test_discovery_error_policy.py` and `test_linux_filesystem_portability.py`.
Matched control: the same five fail on the pristine base commit `250eb1cb` in
the same environment with every change of mine stashed, and all five pass on
3.12 with the changes applied. Reported as a repository finding, not carried as
a result of this work.
