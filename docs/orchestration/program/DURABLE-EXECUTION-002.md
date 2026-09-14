# Durable continuation: executable local protocol

Package: AS-ORCH-DURABLE-CONTINUATION-001. Task:
ATLAS-FROM-DESIGN-TO-VERIFIED-EXECUTION. This extends the existing approved
program, queue, enrollment, lease and checkpoint implementation. It does not
create another scheduler or grant activation authority.

## Approval and actual runtime support

An approved `ProgramTask.execution_steps` list binds ordered unique uppercase
step IDs to fixed argv arrays and per-step acceptance checks. Only the
`local-command` fixture adapter executes this protocol. Generated instructions
for other profiles do not establish executable step support, runtime resume,
provider compatibility or paid-launch authority. A plain local command still
has no conversation-resume capability.

Each step is one existing supervisor attempt/dispatch, with one bounded child.
Task/program/profile attempt and launch limits must cover the declared steps
and any separately authorized verifier. A dispatch intent reserves budget
before spawn; reservation count is not invented command-execution history.
Actual argv/exit status comes from adapter observations. A failed/uncertain
mutating step is not automatically retried because its effect may have landed.

Program bytes, current enrollment/assignment and envelope authority are checked
before each dispatch, including verifier dispatch. A task's named fallback must
be another approved task. After a safely blocked task yields, an eligible
fallback returns through normal selection and authority gates; its name alone
is not a launch grant. Open decisions remain durable and are not re-asked.

## Identity, boundaries and recovery

| Durable boundary | Controller behavior |
| --- | --- |
| No prior execution | Validate authority, write intent, then launch the selected first step. |
| Step intent without observed completion | Preserve uncertainty; reconcile before any mutation or repeat. |
| Observed nonfinal step completion | Require matching attempt/worker/session, paired exited child identity, exact approved command prefix and current authority; dispatch only the next step. |
| All steps observed, final task acceptance not yet sealed | The pure reconciliation lens still reports reconciliation required. The controller may perform explicit **final-acceptance reconciliation**, with current authority/candidate/deadline and matching quiescent proof, without launching another worker. It must actually evaluate final task acceptance; the checkpoint alone never means success. |
| Final acceptance sealed | Complete; no worker replay across future starts. |
| Interrupted approved read-only work | Require the original durable launch identity and proven child exit, unchanged authority and a consistent read-only checkpoint. The prior outcome remains unknown; the approved read may execute again. A live/reused/unknown PID is not a launch grant. |
| Missing, inconsistent or uncertain identity/checkpoint | No automatic worker launch, no signal to a foreign process; preserve evidence for reconciliation. |

The controller writes an uncertain intent checkpoint before a mutating step,
observes child exit and per-step acceptance, then seals completion. Pause gates
the next dispatch without terminating the active step. Restart uses persisted
program/state/checkpoint/launch records, not the previous chat or Python heap.
Tests cut the real controller with `os._exit` before its finally/settlement code,
then use distinct fresh interpreters. Disposable owned child identities are
recorded and checked; no live pilot or other agent process is adopted.

Containment remains the existing explicit governed-root/path/identity contract.
This local protocol is **not an OS sandbox for arbitrary worker code**. Reviewed
zero-model fixtures, path guards and identity-owned cleanup do not establish
machine-wide network isolation or external security certification.

## Context and truthful consumption

Before a governed worker starts, the controller builds at most 8192 UTF-8 bytes
of `ATLAS_PROGRAM_CONTINUATION` JSON. It contains the current task/attempt/worker,
approved-program and envelope digests, previous checkpoint sequence/digest,
last completed and selected next step, known capture count, budgets and deadline.
It is saved as immutable per-attempt evidence before launch. The task's original
instruction is retained separately. Context is data, not fresh authority;
missing changed-file observations remain explicitly unavailable.

Observed adapter duration is stored on the durable attempt. Dispatch timeouts
use the remaining cumulative task wall budget. Checkpoints merge the stronger
durable attempt totals and existing counters; a weaker checkpoint cannot reset
consumption. An interrupted read-only attempt is charged a clearly labelled
conservative wall bound from its recorded start through recovery, including
downtime, not fabricated active CPU time. Missing historical time observations
block further worker dispatch and are labelled as unknown/lower-bound data.
Exactly spent worker reservations do not themselves authorize another worker;
they also do not forbid controller-only final acceptance of completed steps.
Final acceptance does require strictly positive remaining wall time and current
authority/deadline. Pause prohibits new dispatch but permits this settlement
of already completed work; it does not grant a new worker reservation.

Every completed prefix step must retain exactly one matching successful durable
attempt receipt and observed transcript. The last receipt cannot override a
contradictory earlier acceptance. Read-only recovery requires agreeing launch
and intent child IDs; existing checkpoint/attempt process pairs must either be
the empty pre-spawn pair or match the identified launch exactly. Conflicting
records are retained for reconciliation, never overwritten into a restart grant.

## Observed revision versus fixture input

An unreadable current workspace HEAD/TREE is a refusal, not a reason to copy the
approval pin into an observation. An explicit approved-program
`allow_unversioned_fixture: true` exception is available only when all effective
and verifier profiles are local-command fixtures. Its declared placeholder
HEAD/TREE must be labelled **not observed workspace Git identity and not
installed-package provenance**. It cannot authorize a model-backed profile.
Tests of other gates explicitly declare this fixture-only exception; their
assertions are not weakened. A real Git workspace needs no exception.

The Atlas implementation's complete source HEAD/TREE, dirty-state evidence,
interpreter/module provenance and installed-package byte verification are
recorded separately for every acceptance session. An import path alone is not
proof of installation provenance. A fixture placeholder cannot replace those
candidate-bound checks.

## Requirement-to-proof mapping

The original fourteen requirements remain in `DURABLE-CONTINUATION.md` and
`CONTINUATION-DELIVERY.md`. The latter is historical implementation evidence;
its decision-only tests do not prove that a replacement worker actually ran.

| Requirement | Executable coverage |
| --- | --- |
| Killed read-only and mid-task continuation | Fresh-interpreter actual read restart and FIRST-cut/SECOND-cut tests in `test_program_step_execution.py`. |
| Uncertainty, identity, completed no-replay | Native unsafe-boundary tests, retained F01/F02 tests and independent no-Popen controls. |
| Blocked fallback and lease release | Actual hard-block/fallback artifact, single decision and canonical lease projection checks. |
| Empty waiting, admission wake, pause/resume | Existing real idle/wake fixtures plus actual within-task pause/replacement tests. |
| Enrollment and current authority | Retained binding/revocation tests plus changed-program and verifier-deadline execution discriminators. |
| Corrupt state, bounded consumption, truthful context | Native fault injections, remaining-time child execution and observed-history/context checks. |
| Cleanup, legacy finite programs, zero models/network | Retained process/finite suites, reviewed local fixtures and independent controller/child evidence. Network-instrumentation scope is reported explicitly. |

The external completion-002 dossier supplies the actual frozen candidate,
individual run outcomes, independent acceptance, noneditable installation,
operator/resume commands and SHA256SUMS. This source document alone is not any
of those results. Service/reboot procedures remain unexecuted preparation;
strict governance receipt and live activation are separate decisions.
