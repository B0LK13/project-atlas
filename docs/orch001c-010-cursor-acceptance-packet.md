# ORCH001D-012 — Authentic Cursor Dispatch Acceptance Packet

Status: **proposal only, not executed**. This document exists so an owner
can authorize one tightly bounded authentic Cursor CLI dispatch later,
without ambiguity about what would actually run. Nothing in this file
grants execution authority. It is not itself an ORCH001D-012 PASS.

**Correction:** this packet originally covered both ORCH001C-010 and
ORCH001D-012 under the same dispatch-risk rationale. That was wrong.
ORCH001C-010 (Local Windows explicit-completion acceptance) never starts
a real Cursor process — `cursor_bridge.py`'s own import graph has no
dependency on `agent_transport`/`subprocess` at all — and has since been
exercised end-to-end in a disposable directory and recorded `PASS`
(WORKLOG "ORCH001C-010", separately). This packet now covers
**ORCH001D-012 only**, the one item that genuinely requires a real
external Cursor process.

## Why this exists

`resolve_cursor_transport()` (`src/project_atlas/orchestration/agent_transport.py`)
was verified this session to genuinely resolve a live Cursor CLI on this
host (`agent.cmd`, `WINDOWS_CMD_WRAPPER`) with no override, by direct
invocation:
`python -c "from project_atlas.orchestration.agent_transport import resolve_cursor_transport; print(resolve_cursor_transport())"`.
That correction (WORKLOG "Cursor CLI availability correction (ORCH001C-010
/ ORCH001D-012)", PR #624) fixes a prior false `EXTERNAL_BLOCKED` status
that this WORKLOG carried; it does **not** attempt a real dispatch.
**Dependency note:** this packet was authored before PR #624 merged, so
that WORKLOG entry is not yet present on `main` as of this packet's own
base commit — the verification command above is the actual, reproducible
evidence regardless of merge order, and this packet's own classification
line below does not depend on #624 having landed first. Actually invoking
a live Cursor agent process is a materially different, higher-stakes
action (real external-service interaction, unpredictable duration, no
sandboxed blast-radius containment the way a fake runner or
`sys.executable` stand-in has — see the `TARGET_TEST_PROJECT` caveat
below, which is not a security boundary) and requires its own explicit
owner authorization, scoped exactly like every other merge/dispatch
authorization this session has required.

Current classification:

- `ORCH001C_010 = PASS` (see WORKLOG "ORCH001C-010" — not this packet's
  concern; recorded separately, no owner execution authorization needed
  for it)
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
- `TARGET_TEST_PROJECT` — a throwaway `cwd`, never the live repo working
  tree. **Correction:** `build_launch_plan()` only validates that `cwd` is
  a real existing directory (`WORKSPACE_UNSAFE` otherwise) and
  `SubprocessProcessRunner.run()` passes it straight to `Popen` — neither
  establishes a filesystem sandbox, restricted identity, or any OS-level
  containment. A misbehaving Cursor process retains the full filesystem
  access of the account running it; nothing in the inspected transport
  code prevents it from reading or writing outside `TARGET_TEST_PROJECT`.
  Choosing a throwaway directory only bounds *intended* writes and makes
  `ROLLBACK/CLEANUP` simple — it is not a security guarantee, and this
  packet does not claim one. If real isolation (container, VM, restricted
  service account, or similar) is required before an owner is comfortable
  authorizing a dispatch, that isolation does not exist in the code today
  and would need to be provided separately, outside this transport.
- `MAX_DURATION` — recommend the code default (600s) unless the owner
  wants it explicitly shorter; do not raise it above default without a
  specific reason.
- `MAX_DISPATCH_COUNT` — recommend exactly 1 for the first authentic
  acceptance run. No retry loop, no batch.
- `EXPECTED_SIDE_EFFECTS` — none intended: `--mode ask` is a query mode,
  not an edit/agent mode, and no `--force*` flag can reach argv. Real
  side effects would indicate a code defect, not expected behavior. This
  is a claim about the *launch plan's* flags, not a containment guarantee
  — see the `TARGET_TEST_PROJECT` correction above.
- `EXPECTED_COST/USAGE_CLASS` — one real external Cursor CLI invocation,
  bounded by `MAX_DURATION`; exact cost/usage accounting is outside this
  repo's own instrumentation and would need to come from the Cursor
  account/billing surface directly, not from anything Atlas measures.
- `PASS_CRITERIA` — process exits, stdout is well-formed JSON matching
  `--output-format json`'s documented shape, no stderr indicating a
  crash, no side effects observed outside `TARGET_TEST_PROJECT`, and
  captured output on both streams **strictly below** `MAX_CAPTURED_BYTES`
  (64 KiB). **Correction:** do not accept a run at or over the cap as
  pass-with-truncation — `_drain_bounded()` retains only the first
  `MAX_CAPTURED_BYTES` and neither `ProcessRunOutcome` nor the persisted
  dispatch record (which stores only digests of the retained prefix)
  carries a total-byte or truncation flag, so an at-cap result cannot
  actually be distinguished from a coincidentally-exact-boundary result.
  If output does hit the cap, treat the run as inconclusive on output
  completeness, not as a verified pass, until the transport is extended
  with an observable truncation indicator.
- `FAIL_CRITERIA` — timeout without exit (would indicate
  `TimeoutExpired`/kill path did not work as PR #620 fixed it to), any
  side effect outside `TARGET_TEST_PROJECT`, any forbidden-flag/argv-leak
  rejection *not* firing when it should (would indicate a transport
  regression), non-JSON or malformed stdout, or output at/over
  `MAX_CAPTURED_BYTES` on either stream (inconclusive per the correction
  above, not a pass).
- `EVIDENCE_PATH` — exit code and wall-clock duration (already measured
  via `time.monotonic()` per PR #620) recorded in a new WORKLOG entry
  authored *after* the run, not assumed beforehand. **Correction:** do
  not record captured stdout/stderr verbatim in `WORKLOG.md` or any other
  tracked file. The real subprocess inherits nearly the full parent
  environment and its output is untrusted external content — if Cursor
  emits a credential, token, or other sensitive value, verbatim logging
  would persist it in Git history. Run a secret scan over the captured
  output before recording anything from it; store only the scan result,
  bounded/redacted excerpts, or digests of the raw streams, not the raw
  streams themselves.
- `ROLLBACK/CLEANUP` — delete `TARGET_TEST_PROJECT` after the run; no
  other repo state is touched by an ask-mode dispatch, so no other
  rollback should be necessary if `PASS_CRITERIA` holds.

## What this packet does not do

- Does not execute anything.
- Does not claim ORCH001D-012 pass. (ORCH001C-010's `PASS` is recorded
  separately, in WORKLOG "ORCH001C-010" — not a claim of this packet.)
- Does not choose `TARGET_TEST_PROJECT` or fill in the operational bounds
  above — those are the owner's call at authorization time, not this
  document's.
- Does not imply any standing authorization for repeated or automatic
  dispatch. Each authentic run would need its own explicit grant under
  this same bounded-packet discipline, same as every merge authorization
  this session has required per-PR.

`MERGE_AUTHORIZATION = NOT_GRANTED`. `DISPATCH_AUTHORIZATION = NOT_GRANTED`.
