# ATLAS-PRIME-LOCAL-001 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the pinned Prime Agent runtime as a local executor under the existing Atlas supervisor.

**Architecture:** Atlas remains the only mission scheduler, admission authority, ledger, verifier, and acceptance owner. A narrow Python adapter launches and observes the pinned Prime RPC process through bounded stdio, while Prime owns execution inside one admitted attempt. Durable state is recorded in existing Atlas attempt records plus Prime-specific identity bindings.

**Tech Stack:** Python 3.12, Pydantic models, subprocess stdio, JSONL, Node 22.8+, Prime Agent source checkout, pytest, ruff, mypy.

**Spec:** `docs/work-packages/ATLAS-PRIME-LOCAL-001-CAPABILITY-MAP.md` and the user-provided ATLAS-PRIME-LOCAL-001 execution brief.

## Global Constraints

- Prime source is pinned to `5d25a44bd22e1c1fe8321e141cd6c3932563d14c`.
- Atlas is the only scheduler, admission owner, budget ledger, verifier, and acceptance authority.
- RPC uses LF JSONL; CRLF input is accepted; U+2028/U+2029 do not delimit records.
- ACK means accepted or queued, never completed or accepted.
- No recursive native spawn is enabled without host-side admission.
- Provider credentials remain outside model-readable state and only existing grants may be used.
- Model-free smoke, real-provider execution, independent verification, and installation are separate claims.

### Task 1: Runtime identity and protocol contract

**Files:**
- Create: `src/project_atlas/orchestration/program/adapters/prime_agent.py`
- Create: `tests/unit/test_prime_agent_adapter.py`
- Modify: `src/project_atlas/orchestration/program/profiles.py`
- Modify: `src/project_atlas/orchestration/program/adapters/__init__.py`

Implement the adapter capabilities and bounded JSONL parser before wiring the supervisor. The parser must reject malformed and over-sized frames, accept CRLF, and preserve Unicode separators inside JSON strings.

### Task 2: Supervisor/runtime registration

**Files:**
- Modify: `src/project_atlas/orchestration/program/supervisor.py`
- Modify: `src/project_atlas/orchestration/program/runtimes.py`
- Modify: `src/project_atlas/orchestration/program/credentials.py`
- Create: `tests/unit/test_prime_agent_registration.py`

Register the adapter as an explicit runtime. Reuse existing request/outcome, leases, limits, cancellation, and acceptance paths. Do not add a second scheduler or persistent task store.

### Task 3: Reconnect, recovery, and evidence binding

**Files:** existing adapter/supervisor/store modules and focused tests.

Journal dispatch before effects, preserve stable command/session identities, reject stale generations, and classify unknown side effects as uncertain. Add bounded lifecycle tests for bridge loss, daemon restart, worker crash, supervisor restart, pause, stop, and deadline.

### Task 4: Installation and manifest

**Files:** `scripts/prime-local-001-install.sh`, `docs/orchestration/program/PRIME-LOCAL-001-RUNBOOK.md`, runtime manifest fixture.

Provide a reproducible pinned source install in a new isolated path using `npm ci`, explicit Node/Python checks, supported config/session paths, and secret-free hashes. Do not enable services or import credentials.

### Task 5: Vertical slice, verifier, knowledge, and UI evidence

Use the existing Atlas program CLI and read projections to execute a small real task, then run tests, independent verification, knowledge readback, and resume-after-detach checks. Keep unproved provider, deployment, CI, and human-IV claims open.
