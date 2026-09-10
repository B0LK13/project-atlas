# AS-ACCEPT-005 — reusable mission acceptance

Run one command from a clean checkout and get: prerequisites checked, pins
verified, a set of permitted disposable missions executed as real
subprocesses, evidence you can read and evidence a machine can read.

```bash
git clone <repo> && cd project-atlas
git checkout feat/atlas-mission-acceptance-005
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

python scripts/acceptance/mission_accept.py --i-authorize-bounded-execution \
    --json-out /tmp/acceptance.json
```

Nothing else is required — no vault, no Studio packet, no environment
variables, no files from a previous session.

## What authorizes the subprocesses

**Not Studio.** Two separate things, both owned by the caller:

| Input | Value | Where it comes from |
|---|---|---|
| execution permission | `--i-authorize-bounded-execution` or `ATLAS_ACCEPT_EXECUTE=1` | the operator, per run |
| `trusted_policy` | `{"MERGE_AUTHORIZATION": "NO"}` | a literal in `mission_accept.py` |

Without the flag the runner does preflight and planning only and says so
(`execution_permission = NOT GRANTED (planning only)`).

A Studio task-context packet (`--packet`) is **optional context**. It can
cause a run to be **refused** — stale, wrong actor, no supported action, or a
packet that has stopped disclaiming authority — but it can never authorize
one. The evidence records `studio_can_authorize: false` on every run.

## Preflight — what it refuses

| Check | Why it exists |
|---|---|
| Python ≥ 3.12, `git` present | basic prerequisites |
| repository identity | resolves the real toplevel, records head and tree |
| **import leakage** | if `project_atlas` resolves *outside* this checkout, the run is refused — subprocess tests resolve through the editable install, **not** `PYTHONPATH`, so a stale venv silently exercises a different working tree |
| partial assembly | names the missing module (`mission_bridge.py`, `orchestration/mission`, …) rather than failing later |
| component pins | `#791`/`#786`/`#781`/`#789` reported present/absent; `--strict-pins` makes absence fatal |

Preflight failure exits **2** and preserves diagnostics; nothing is executed.

## Missions — derived from risks, not a target count

| Label | Risk it covers | Expected task outcome |
|---|---|---|
| `passing_change` | a real change plus a test that proves it | **succeeds** |
| `intentional_test_failure` | the command spawns and exits cleanly at the OS level while the *task* fails | **fails** (`rc=1`, `NONZERO_EXIT`) |
| `real_checkout` | workspace **is** a disposable git checkout — the usage #789 names, where the lease guards a real tree and operational state must stay under `.atlas-mission/` | **succeeds** |
| `interrupted_task` | worker SIGKILLed mid-adapter | **fails**, and must not auto-replay |

**Command success is not task completion.** `intentional_test_failure` exists
to keep that distinction honest: the subprocess ran perfectly and the
engineering task still failed. A mission that *expects* failure would be a
regression if it started passing.

## Blast radius

Every workspace lives under one run-scoped root (`/tmp/atlas-accept-*`) and is
removed by the same run. Disposable checkouts are created with `git worktree
add` and removed with `git worktree remove`, so **no registration is left in
the caller's `.git/worktrees`** — the earlier `atlas_one_workflow.py` leaked
both. Verified across a full run: worktree count unchanged (125 → 125), zero
leftover roots. `--keep` retains workspaces and says so in the report.

Nothing outside the run root is written. Caller files are never touched.

## Known defect this runner works around

`start_mission_run`'s **default** idempotency key is
`f"{mission_id}:{base_head}"` and does not include the adapter command. Two
different commands at the same commit collide: the second is silently
deduplicated **and returns the first's result**.

```
run A  dedup=False  reported command=a.sh
run B  dedup=True   reported command=a.sh     <- caller asked for b.sh
what actually ran: ['RAN_A']
```

Owned by **#789**; reported with a standalone reproduction, not repaired here.
This runner always passes an explicit key including an adapter digest — a
**mitigation in this caller, not a fix**.

## Boundaries probed, and what held

| Case | Behaviour | Verdict |
|---|---|---|
| corrupt checkpoint | `MALFORMED` → refused, `UNKNOWN_CHECKPOINT_UNSAFE_TO_RETRY` | correct |
| missing checkpoint | `ABSENT` → `NO_RUN_FOUND`, safe to retry | correct |
| wrong-workspace attribution | refused on recorded-workspace mismatch | correct |
| repeated resume after a confirmed result (3×) | stable dedup, same `run_id` | correct |
| SIGKILL mid-adapter | `UNCERTAIN_REQUIRES_RECONCILIATION`, `safe_to_retry=False`, next run **blocked** | correct |
| stale context | `ContextStaleError` on a genuinely mutated ADR | correct |
| same key, **different command** | silently deduplicated, misattributed | **defect (#789)** |
| different mission, same workspace | prior checkpoint overwritten | limitation, appears intentional |

## Scope of the evidence — read before quoting it

- **Resume proves one measured action.** A shell script appending `EFFECT-RAN`
  to a file: same key across a fresh process → count stayed **1**; different
  key → **2**. That is the checkpoint/idempotency contract *for that action*.
  It does **not** generalize to arbitrary external effects — network calls,
  API writes, anything the checkpoint cannot observe are out of scope.
- **Linux-local unless a CI job says otherwise.** All local runs were Linux
  x86_64 / CPython 3.12.14. Windows evidence, where it exists, comes only from
  the `windows-latest` CI job. macOS was never exercised.
- **"Clean-environment reproduction", not a second operator.** The clean-venv
  runs described here were performed by the same session on the same machine.
  No genuinely separate operator has run this.
- `atlas validate` still exits 1 on this repository (unmasked code span in
  compiled claim text). Pre-existing, owned by **#700**, not fixed here.
