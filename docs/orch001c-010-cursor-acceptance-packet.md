# ORCH001C-010 / ORCH001D-012 — Authentic Cursor Dispatch Acceptance Packet

Status: **proposal only, not executed**. This document exists so an owner
can authorize one tightly bounded authentic Cursor CLI dispatch later,
without ambiguity about what would actually run. Nothing in this file
grants execution authority. It is not itself an ORCH001C-010/ORCH001D-012
PASS.

## Why this exists

`resolve_cursor_transport()` (`src/project_atlas/orchestration/agent_transport.py`)
was verified this session to genuinely resolve a live Cursor CLI on this
host (`agent.cmd`, `WINDOWS_CMD_WRAPPER`) with no override — see WORKLOG
"Cursor CLI availability correction (ORCH001C-010 / ORCH001D-012)". That
correction fixed a false `EXTERNAL_BLOCKED` status; it did **not** attempt
a real dispatch. Actually invoking a live Cursor agent process is a
materially different, higher-stakes action (real external-service
interaction, unpredictable duration, no bounded blast radius the way a
fake runner or `sys.executable` stand-in has) and requires its own
explicit owner authorization, scoped exactly like every other merge/dispatch
authorization this session has required.

Current classification:

- `ORCH001C_010 = AVAILABLE_OWNER_EXECUTION_AUTH_REQUIRED`
- `ORCH001D_012 = AVAILABLE_OWNER_EXECUTION_AUTH_REQUIRED`

## What would actually run

The transport's own `build_launch_plan()` already constrains the shape of
any dispatch it builds — this packet does not invent new bounds, it
documents the ones the code enforces plus the operational bounds an owner
would additionally set:

| Field | Value (code-enforced) |
|---|---|
| `COMMAND` (flags) | `READ_ONLY_CURSOR_FLAGS = ("--print", "--output-format", "json", "--mode", "ask")` — non-mutating ask-mode only |
| Forbidden flags | `FORBIDDEN_CURSOR_FLAGS = {"--force", "--force-allow-http", "-f"}` — rejected before spawn if present |
| Prompt transport | stdin only; never appears in argv (`build_launch_plan` raises `PROMPT_REJECTED` if it would leak into argv) |
| `MAX_PROMPT_CHARS` | 8,192 |
| Default `timeout_seconds` | 600 (`DEFAULT_TIMEOUT_SECONDS`); hard bound 1–86,400 |
| Captured output cap | 64 KiB per stream (`MAX_CAPTURED_BYTES`), bounded-drain (no unbounded memory growth) — this session's own PR #620 fix |

Operational bounds an owner authorization would additionally fix at grant
time (not yet chosen — placeholders below, to be filled in by the actual
authorization, not by this document):

- `EXACT_ATLAS_HEAD` — the exact commit the dispatch runs against. As of
  this packet's authoring: `53fbc9f4bc79ce84bebd3b1c4406637b6b9ab2fe`
  (current `main`). **Must be re-confirmed as current at authorization
  time** — main has moved multiple times per hour this session.
- `TARGET_TEST_PROJECT` — a throwaway/isolated `cwd` (`build_launch_plan`
  already requires `cwd` to be a real existing directory —
  `WORKSPACE_UNSAFE` otherwise), never the live repo working tree, so a
  misbehaving or slow dispatch cannot mutate anything this session
  depends on.
- `MAX_DURATION` — recommend the code default (600s) unless the owner
  wants it explicitly shorter; do not raise it above default without a
  specific reason.
- `MAX_DISPATCH_COUNT` — recommend exactly 1 for the first authentic
  acceptance run. No retry loop, no batch.
- `EXPECTED_SIDE_EFFECTS` — none intended: `--mode ask` is a query mode,
  not an edit/agent mode, and no `--force*` flag can reach argv. Real
  side effects would indicate a code defect, not expected behavior.
- `EXPECTED_COST/USAGE_CLASS` — one real external Cursor CLI invocation,
  bounded by `MAX_DURATION`; exact cost/usage accounting is outside this
  repo's own instrumentation and would need to come from the Cursor
  account/billing surface directly, not from anything Atlas measures.
- `PASS_CRITERIA` — process exits, stdout is well-formed JSON matching
  `--output-format json`'s documented shape, no stderr indicating a
  crash, no side effects observed outside `TARGET_TEST_PROJECT`, captured
  bytes at or under `MAX_CAPTURED_BYTES` (or correctly reported as
  truncated with the right boundary behavior per PR #620's regression
  suite).
- `FAIL_CRITERIA` — timeout without exit (would indicate
  `TimeoutExpired`/kill path did not work as PR #620 fixed it to), any
  side effect outside `TARGET_TEST_PROJECT`, any forbidden-flag/argv-leak
  rejection *not* firing when it should (would indicate a transport
  regression), non-JSON or malformed stdout.
- `EVIDENCE_PATH` — full captured stdout/stderr, exit code, wall-clock
  duration (already measured via `time.monotonic()` per PR #620),
  recorded verbatim in a new WORKLOG entry authored *after* the run, not
  assumed beforehand.
- `ROLLBACK/CLEANUP` — delete `TARGET_TEST_PROJECT` after the run; no
  other repo state is touched by an ask-mode dispatch, so no other
  rollback should be necessary if `PASS_CRITERIA` holds.

## What this packet does not do

- Does not execute anything.
- Does not claim ORCH001C-010 or ORCH001D-012 pass.
- Does not choose `TARGET_TEST_PROJECT` or fill in the operational bounds
  above — those are the owner's call at authorization time, not this
  document's.
- Does not imply any standing authorization for repeated or automatic
  dispatch. Each authentic run would need its own explicit grant under
  this same bounded-packet discipline, same as every merge authorization
  this session has required per-PR.

`MERGE_AUTHORIZATION = NOT_GRANTED`. `DISPATCH_AUTHORIZATION = NOT_GRANTED`.
