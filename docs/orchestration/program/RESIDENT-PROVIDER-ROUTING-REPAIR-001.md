# Resident provider routing repair

Candidate: `HEAD=cb8812bd323e7a84f6f94026805094325efed0c3`,
`TREE=adc6c29c81225973a171d020144b001eefc7af6c`.

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
