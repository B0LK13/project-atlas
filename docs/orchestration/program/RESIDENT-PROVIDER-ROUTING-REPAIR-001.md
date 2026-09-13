# Resident provider routing repair

Candidate: `HEAD=7b9ace01f0bc06931f1191f8912abda1f7935953`,
`TREE=2214d53a79094c16d96dd07a41341d3f701f1b69`.

## Defect and repair

The predecessor rejected every effective or verifier profile whose adapter was
not `local-command` in `ResidentDispatcher._run_entry`, before constructing
`ProgramSupervisor`, with `MODEL_DISPATCH_DISABLED`. The shipped Claude Code
adapter therefore existed but was unreachable from an admitted resident
queue entry. The successor removes only that blanket resident rejection. The
resident still verifies the queue and program, resolves active enrollment, and
constructs the existing `ProgramSupervisor`; that supervisor performs the
normal preflight, authority, workspace, budget, attempt, PID/start-identity,
cleanup and result handling before calling the selected adapter.

`model_backed_dispatch` is now an evidence status (`ENABLED` for an admitted
non-fixture profile, otherwise `DISABLED`) in the heartbeat, restart witness,
events, capsule and envelope. It is not an authorization grant and does not
launch a provider.

## Candidate-bound checks

* The predecessor control failed because the resident factory was not reached
  for a valid Claude Code profile (`MODEL_DISPATCH_DISABLED`).
* The successor control reached the resident supervisor factory for the same
  profile and candidate-bound revision fixture.
* The shipped adapter factory maps `claude-code` to `ClaudeCodeAdapter`; no
  generic shell substitution is used.
* Existing containment, PID-reuse, enrollment, restart, no-replay and durable
  continuation suites remain green. No provider process or model call was
  started by these controls.

## Boundary

This proves adapter reachability, not provider acceptance. A real Claude Code
probe remains a separate, explicitly authorised operation. Unsupported
profiles fail during profile loading/adapter construction before a provider
launch; missing enrollment or current authority remains a zero-launch result.
