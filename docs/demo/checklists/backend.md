# Backend demo gate checklist — AS-DEMO-2.1-001

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> Runbook: [`../BACKEND-SUITE.md`](../BACKEND-SUITE.md)
>
> Certificate target: **TECHNICAL DEMO — VERIFIED** (demo lane only)
>
> This checklist **never** asserts `RELEASE CERTIFIED` or authentic
> `PILOT PASS`.

## Run identity

| Field | Value (fill live) |
|---|---|
| Operator | |
| Date (local) | |
| Tip `HEAD` | `git rev-parse HEAD` → |
| TREE (optional) | |
| Branch / worktree | |
| Host OS | Windows / Linux / macOS |
| Python | `python --version` → |
| Mode banner printed? | Yes / No |

Honest banner required:

```text
CERTIFICATE TARGET: TECHNICAL DEMO — VERIFIED
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
NOT RELEASE EVIDENCE
```

## B0 — Install

| Step | Command | Exit | Notes |
|---|---|---|---|
| Clean clone / dedicated worktree | — | ☐ | No hidden developer vault for certification |
| Create venv | `python -m venv .venv` | ☐ | |
| Activate | `.\.venv\Scripts\Activate.ps1` or `source .venv/bin/activate` | ☐ | |
| Install | `pip install -e ".[dev]"` | ☐ | |
| Sanity | `atlas version` | ☐ | |

## B1 — Pytest subset (rehearsal only)

Insufficient alone for VERIFIED.

```text
python -m pytest tests/integration/test_cli.py tests/integration/test_core_vertical_slice.py tests/integration/test_core_claims_authority_conflicts.py tests/unit/test_scaffold.py -q --tb=short
```

| Metric | Live value |
|---|---|
| collected / selected | |
| passed | |
| failed | |
| skipped | |
| duration | |
| exit code | |
| Pass? | ☐ Yes · ☐ No |

## B2 — Full backend suite (required for VERIFIED)

| Gate | Command | Exit 0? | Duration | Notes |
|---|---|---|---|---|
| Ruff | `python -m ruff check .` | ☐ | | |
| Mypy | `python -m mypy src` | ☐ | | |
| Pytest (full) | `python -m pytest` | ☐ | | |

Pytest live summary (full suite — **do not** paste historical counts):

| Metric | Live value |
|---|---|
| collected | |
| passed | |
| failed | |
| skipped | |
| duration | |
| `coverage.xml` present? | ☐ Yes · ☐ No · ☐ N/A |

## B3 — Atlas CLI smoke (AT-001)

Disposable vault under `.tmp/` only.

| Step | Command / check | Pass? |
|---|---|---|
| Help | `atlas --help` | ☐ |
| Version | `atlas version` | ☐ |
| Dry-run init | `atlas init --output .tmp/atlas-demo-cli-smoke --dry-run` | ☐ |
| Real init | `atlas init --output .tmp/atlas-demo-cli-smoke` | ☐ |
| `index.md` exists | file present | ☐ |
| `00-system/vault-charter.md` exists | file present | ☐ |

## B4 — Findings

| ID | Severity | Summary | Blocks VERIFIED? | Status |
|---|---|---|---|---|
| DEMO-FINDING- | CRITICAL / HIGH / MEDIUM / LOW | | Yes if C/H | open / fixed |

No open CRITICAL or HIGH → required for backend VERIFIED contribution.

## B5 — Certificate criteria decision (backend)

| Criterion | Met? |
|---|---|
| B0 install on clean/dedicated tree | ☐ |
| Honest DEMO / not-release banner recorded | ☐ |
| Ruff exit 0 | ☐ |
| Mypy exit 0 | ☐ |
| Full pytest exit 0 + live counts captured | ☐ |
| CLI smoke exit 0 | ☐ |
| No open CRITICAL/HIGH demo findings | ☐ |

### Backend contribution stamp

| Field | Value |
|---|---|
| Backend gates support **TECHNICAL DEMO — VERIFIED**? | ☐ YES · ☐ NO |
| `RELEASE CERTIFIED`? | **NO** (always) |
| Authentic `PILOT PASS`? | **NO** (always) |
| May cite as `v2.1.0` release evidence? | **NO** (always) |

Operator sign-off (name / tip):

```text
________________________________  HEAD=____________________
```

## Explicit non-claims

- Passing this checklist is a **demo-lane** backend gate only.
- Sibling frontend / API-MCP / ADV cert packages must still pass for a
  full-lane **TECHNICAL DEMO — VERIFIED** stamp.
- `DEMO_FIXTURE` success ≠ authentic estate certification.
- Pilot remains `DORMANT_BLOCKED` until `AUTHENTIC_ESTATE_ROOT_AVAILABLE`.
