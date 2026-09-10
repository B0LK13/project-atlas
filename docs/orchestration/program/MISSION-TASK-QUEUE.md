# ATLAS-SYSTEMWIDE-CONTINUOUS-EXECUTION — mission task queue

Durable queue for the implementing session. Package
`AS-ORCH-PROGRAM-SUPERVISOR-001`, lane `feat/as-orch-program-supervisor-001`,
worktree `~/Projects/project-atlas-worktrees/program-supervisor`, base
`b87b4a22`.

Scope note (owner, 2026-09-10): one runtime and one worker are the first
validation milestone, **not** the final product scope. The objective is
continuous execution across all enrolled Atlas agents and supported runtimes.

## M1 — Prove the supervisor  ✅ COMPLETE

- [x] T01 Repository inventory + reuse map (`REUSE-MAP.md`)
- [x] T02 `models.py` — program, task, limits, acceptance, attempt records
- [x] T03 `profiles.py` — shared defaults, role profiles, narrowing-only overrides
- [x] T04 `store.py` — durable state, atomic writes, append-only fsynced event log
- [x] T05 `adapters/base.py` — adapter seam + outcome contract
- [x] T06 `adapters/local_command.py` — labelled fixture worker + fault injection
- [x] T07 `adapters/claude_code.py` — real Claude Code CLI adapter
- [x] T08 `acceptance.py` — locally observed acceptance, never worker-reported
- [x] T09 `waiting.py` — external events over `sdk.external_observers`
- [x] T10 `supervisor.py` — the cycle
- [x] T11 `cli.py` — validate / start / status / cancel / reconcile / events
- [x] T12 Acceptance program (43 tests, deterministic workers + fault injection)
- [x] T13 Regression tests for races and uncertain outcomes
- [x] T14 Real-runtime demonstration (`evidence/REAL-RUNTIME-DEMO.md`)
- [x] T15 Documentation (`README.md`, `PERMISSIONS.md`)
- [x] T16 Gates: ruff clean, mypy clean (419 files), targeted pytest green

## M2 — Support Codex and Claude  ✅ COMPLETE

- [x] T20 Inventory installed runtimes and existing adapters before adding any
      (existing: Cursor SDK `sdk/backend.py`, cursor-agent
      `sdk/cli_execution_port.py`, generic `local_process_transport.py`;
      `atlas3/memory/codex.py` is a history connector, not an execution
      adapter. No Codex execution adapter existed)
- [x] T21 Codex adapter against the verified `codex exec` interface
      (`codex-cli 0.153.4`), including streamed JSONL and thread-id recovery
- [x] T22 Capability contracts: `accepts_assigned_session` added and consulted;
      per-runtime launch, output, permission and resume behaviour encoded
- [x] T23 Controlled handoff (`program handoff`) — neither runtime attaches to
      a live session; an operator enrols a STORED session and the next dispatch
      continues it in a new supervised run
- [x] T24 `program runtimes` + `SUPPORT-MATRIX.md`; unsupported capabilities
      named, not omitted
- [x] T25 Real Codex demonstration (`evidence/REAL-RUNTIME-DEMO-CODEX.md`)
- [x] T26 31 further tests (`test_orchestration_program_runtimes.py`)

## M3 — Shared enrollment  ✅ COMPLETE

- [x] T30 `agent enroll` — one registry holding identity, role, runtime,
      workspace and narrowing-only profile overrides
- [x] T31 `agent assign` (binding proved before it is recorded) + `agent launch`
- [x] T32 Four identities separated and reported with their lifetimes
      (`agent status`); a dead supervisor releases no ownership
- [x] T33 Existing sessions enter only through `program handoff`; no live
      process is ever adopted
- [x] T34 Verification separation re-checked after enrollment substitution
- [x] T35 16 further tests (`test_orchestration_program_enrollment.py`)

## M4 — Concurrent agents

- [ ] T40 Multiple workers through the existing DAG ownership mechanisms
- [ ] T41 Conflicting-write and duplicate-dispatch prevention under concurrency
- [ ] T42 Frozen candidates and independent-verifier separation respected
- [ ] T43 Completion releases/transitions ownership and triggers next selection

## M5 — Durable execution

- [ ] T50 Run under the repository's supported service mechanism
- [ ] T51 Explicit installation and activation
- [ ] T52 Recovery after supervisor restart, agent exit, UI closure, host interrupt
- [ ] T53 Quota, credentials, hook failure, unavailable tools, external gates as states
- [ ] T54 Runtime switching only when authorized and compatible

## M6 — Central control

- [ ] T60 Stable read-only status contract for Atlas Studio
- [ ] T61 Pause / resume / cancel / limits / intervention through governance
- [ ] T62 Closing Studio must not terminate supervisor-owned work

## M7 — Other runtimes

- [ ] T70 Inventory remaining runtimes actually used in Atlas
- [ ] T71 Adapters per verified capability and practical demand
- [ ] T72 No universal-support claim from a generic subprocess wrapper

## Systemwide acceptance

- [ ] Codex and Claude workers progressing through separate approved queues
      under one supervisor, with ownership protection, restart recovery,
      explicit limits, and no user prompt between eligible tasks
- [ ] Support reported per runtime and environment
