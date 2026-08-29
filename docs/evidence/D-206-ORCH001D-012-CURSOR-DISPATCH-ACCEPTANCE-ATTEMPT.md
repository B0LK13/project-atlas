# D-206 — ORCH001D-012 authentic Local Windows Cursor agent dispatch: genuine acceptance attempt, real precondition gap found

## What this is

A genuine, non-simulated attempt at `ORCH001D-012` ("Authentic Local
Windows Cursor agent dispatch acceptance", `docs/backlog.md` line 516) —
not a fixture, not a mock `ProcessRunner`. This record is honest about the
outcome: the dispatch did not reach a successful agent response, and the
reason is now precisely characterized rather than left as an open
checkbox.

No pre-existing "ORCH001D-012 acceptance packet" document was found
anywhere in the repository (searched `docs/`, `WORKLOG.md`) before this
attempt — only the single backlog checklist line. The bounds used here
(exactly one dispatch, ask-mode, throwaway cwd, bounded prompt, bounded
timeout, no merge/destructive authority, no credential disclosure) come
from the owner's own directive text for this task, cross-checked against
`agent_transport.py`'s actual, structurally-enforced constants
(`READ_ONLY_CURSOR_FLAGS`, `FORBIDDEN_CURSOR_FLAGS`,
`CursorLaunchPlan.cursor_mode: Literal["ask"]`,
`CursorLaunchPlan.uses_force: Literal[False]`) — not invented, and not
weakened.

## Method

Called the real transport code directly (`agent_transport.build_launch_plan`
+ `agent_transport.SubprocessProcessRunner`) — the same functions
`AS-ORCH-001D`'s dispatcher itself uses — rather than going through
`atlas orchestrator dispatch-once`, because no real *eligible* WorkNode
exists yet that would route to the external-process path: `discover()`
today only ever produces the `IN_PROCESS` pilot node (see
`AutonomousGovernor._pilot_node`, `execution_host_class =
ExecutionHostClass.IN_PROCESS`), which never reaches
`agent_transport.py` at all. A genuine ORCH001D-012 exercise is
necessarily a deliberately-constructed one-off today, the same way
`ORCH001C-010` was.

```
resolved = resolve_cursor_transport()  # -> agent @ ...\cursor-agent\agent.cmd (windows_cmd_wrapper)
throwaway = <fresh empty tempfile.mkdtemp() directory, no relation to any repo>
plan = build_launch_plan(resolved, PROMPT, cwd=throwaway, timeout_seconds=60)
outcome = SubprocessProcessRunner().run(ProcessRunRequest(
    argv=tuple(plan.argv), cwd=throwaway, timeout_seconds=60,
    env=sanitize_inherited_env(), stdin=plan.stdin_payload.encode("utf-8"),
))
```

`PROMPT = "What is 7 multiplied by 6? Reply with only the number, nothing else."`
— trivial, verifiable, non-sensitive; chosen so the evidence here needs no
redaction.

Bounds actually verified on the constructed plan before executing, not
assumed:

```
PLAN_CURSOR_MODE = ask
PLAN_USES_FORCE = False
PROMPT not in plan.argv (assert passed — prompt is stdin-only)
PLAN_TIMEOUT_SECONDS = 60
```

## Result — genuine, not fabricated

Two real, independent subprocess invocations were made (a first run whose
Python-side console print of `stderr` crashed on a Windows `cp1252`
encoding error *after* the subprocess had already completed and the
throwaway directory had already been cleaned up in `finally`; a second,
identical run to capture the same bytes safely to a file instead of the
console — both are real `cursor-agent` invocations, not retries of a
failed launch):

```
RESOLVED_EXECUTABLE = agent @ C:\Users\Admin\AppData\Local\cursor-agent\agent.cmd (windows_cmd_wrapper)
PLAN_ARGV = (cmd.exe, /d, /c, ...\agent.cmd, --print, --output-format, json, --mode, ask)
EXIT_CODE = 1
TIMED_OUT = False
DURATION_MS ≈ 3700–7100 (two runs)
STDOUT = <empty>
STDERR =
  ⚠ Workspace Trust Required

    Cursor Agent can execute code and access files in this directory.
    Do you trust the contents of this directory?

      C:\Users\Admin\AppData\Local\Temp\orch001d012-throwaway-...

    To proceed, you can either:
      • Run 'agent' interactively to decide
      • Pass --trust, --yolo, or -f if you trust this directory
```

`cursor-agent` itself (confirmed from its own `--help`, not assumed)
refuses to run non-interactively against a directory it has never seen
before, unless given `--trust`, `--yolo`, or `-f`/`--force` — and all
three are exactly the flags `agent_transport.FORBIDDEN_CURSOR_FLAGS`
correctly, deliberately refuses to ever include in a launch plan. There is
no separate `cursor-agent trust <path>` subcommand or non-interactive
trust-grant mechanism (checked the full `--help` command list: `login`,
`logout`, `mcp`, `plugin`, `worker`, `status`/`whoami`, `models`,
`bedrock`, `about` — nothing else). Workspace trust for a directory is
established only by an interactive session choosing to trust it once
(recorded as a per-directory `.workspace-trusted` marker under
`%USERPROFILE%\.cursor\projects\...`), or by passing one of the forbidden
flags.

## Why this is the right outcome, not a bug to route around

`agent_transport.py`'s own module docstring states
`UNTRUSTED_TEXT_REACHES_WINDOWS_COMMAND_STRING = NO` and
`CURSOR_PROSE_CAN_CHOOSE_NEXT_ROUTE = NO` as its core guarantees; refusing
to silently pass `--trust`/`--force`/`-f`/`--yolo` on a fresh, never-seen
directory is the same discipline applied one layer up, at the vendor
CLI's own consent boundary, not a gap in it. Using one of the forbidden
flags here to force this exercise to "succeed" would have been exactly
the kind of scope-widening the bounding directive for this task explicitly
forbade ("Do not weaken acceptance criteria"; "no scope expansion").

## Honest classification

```
ORCH001D_012_DISPATCH_ATTEMPTED = YES (genuine, two real subprocess runs)
ORCH001D_012_RESPONSE_RECEIVED = NO
ORCH001D_012_BLOCKER = WORKSPACE_TRUST_REQUIRED (vendor CLI precondition, not an Atlas defect)
ORCH001D_012_ACCEPTANCE = NOT_YET_SATISFIED
TRANSPORT_LAYER_BEHAVED_CORRECTLY = YES (resolved real executable, built a
  correctly-bounded ask-mode/no-force plan, launched a real process,
  captured real bounded output, never used a forbidden flag)
FORBIDDEN_FLAG_USED = NO
```

## What would actually close this

Not a code change to Atlas. An interactive `cursor-agent` session (a human,
or an agent running interactively rather than under `--print`) choosing
"trust this directory" once for a specific throwaway directory, after
which the exact same non-interactive `--print --mode ask` dispatch used
here would run against that now-trusted directory without needing any
forbidden flag. That interactive step is outside what this pass can
perform on its own — it requires the same kind of one-time human consent
gate as any other IDE/tool's first-run trust prompt.

## Certification state

Documentation-only; no source code changed. Not self-certified as
"acceptance passed" — it explicitly did not. This is the same honest,
open-and-precisely-scoped recording convention as D-204: the gap is real,
now exactly characterized, and left open rather than talked around.
