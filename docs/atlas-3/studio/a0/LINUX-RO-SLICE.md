# AS-STUDIO-A0-001 — Linux read-only slice

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
NO_CLI_TEXT_PARSING_AS_PROTOCOL
```

## What this is

Smallest Linux RO vertical slice: `scripts/atlas_studio/` +
`scripts/atlas-studio.py`. Builds `ATLAS_STUDIO_SNAPSHOT_V1` by **calling**
existing F14/F15 builders programmatically (not by parsing `atlas-dag`
stdout).

## Prerequisites

```bash
# from repo root (this worktree)
pip install -e ".[dev]"   # or use existing .venv
# optional live path:
gh auth status            # when probing live GitHub
```

## Commands

```bash
.venv/bin/python scripts/atlas-studio.py doctor --json
.venv/bin/python scripts/atlas-studio.py snapshot --json
.venv/bin/python scripts/atlas-studio.py snapshot --agent ubuntu-main --json
```

Unit tests inject control_view / telemetry / residuals — no network.

## Honesty when GitHub unavailable

If `gh` is missing, unauthenticated, or the DAG Control issue cannot be
read:

- Live snapshot path returns `slice_status` of `UNKNOWN` or `DEGRADED`
- Exit code may be non-zero for hard failures, or `0` with honest UNKNOWN
  panels when builders degrade closed
- Studio must **not** invent runnable lanes, ownership, or merge authority

```text
GH_UNAVAILABLE => UNKNOWN/DEGRADED (honest), never fabricated truth
```

## Crash contract

Exiting the `atlas-studio` process must not call any daemon kill / agent
task termination API. Agent work continues under `ATLAS_DAEMON` /
coordination runtime independently of Studio process lifetime.
