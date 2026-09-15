# Autonomy Policy: Governed RSI Loop

- Decisions: `D-ATLAS-RSI-GOVERNED-LOOP-001` (loop), `D-ATLAS-AUTONOMY-LADDER-001`
  (authority ladder), and the owner's `lanes.fallback` rule of 2026-09-15 (section 4.4).
- Status: **DRAFT**, proposed by the executor on branch `autonomy/scaffold`. It becomes
  binding when the owner merges it. From then on only the owner edits this file.
- Pin: `policy_sha` = SHA-256 of this file's exact LF bytes
  (`python autonomy/tools/preflight.py sha`). The pin is recorded in `autonomy/loop.yaml`
  and in every grant. A grant whose `policy_sha` differs from the current file is void.

## 1. Purpose and boundary

A bounded recursive self-improvement loop: agents develop Atlas one iteration at a time,
with an executor, an isolated verifier, an instrument reviewer and a supervisor gate, and a
grant between iterations. This is the "factory" tier dogfooding the "brain". It is not
Strategy C.

The loop **may improve its own instruments** (directives, checklists, tests, skills).
It **may never improve its own authority** (this policy, `loop.yaml`, the gate tool, CI,
release workflows, secrets, agent instruction files, the level it runs at).

Autonomy is earned, not standing. The owner rejected continuous autonomy on 2026-09-02 and
this policy does not override that. Each level of self-governance (section 11) is unlocked
only by an owner-committed edit of the autonomy level, triggered by ledger evidence the loop
produces. The loop produces the evidence; the owner turns the ratchet.

## 2. Invariants

1. Repository truth over conversation memory. Every role reads grant, directive, policy
   hash and base SHA from the repository. Nothing passes between agents through chat memory.
2. No loop role merges to `main`. At levels 0 and 1 no loop role merges to
   `autonomy/staging` either. Only the owner, or a merge agent the owner separately
   authorizes, merges.
3. Every claim in a return packet, cert, drift report, verdict or audit cites a commit SHA,
   a file path (optionally `:line`), or a CI run URL. A claim without an evidence pointer is
   an automatic REJECT.
4. Kill switch: if `autonomy/HALT` or `autonomy/HALT-REQUEST` exists (in the working tree or
   on the grant ref) the loop stops before its next step. Any role may create either file.
   Only the owner removes them.
5. Autonomy is granted per iteration by a verifiable grant, never standing. No valid grant
   means no iteration.
6. Roles stay separated: orchestrate, execute, verify and supervise are never collapsed into
   one agent. Every commit declares exactly one `Atlas-Role` trailer, a branch carries commits
   of one role only, and no role other than the executor changes `src/**` or `tests/**`.
7. At every level the owner alone holds three powers: edit this file (including the
   autonomy level), write or remove `HALT`, and merge to `main`.
8. Truth boundaries hold: `PROMOTE_ELIGIBLE != MERGED`, `CONTINUE != MERGE AUTHORIZED`,
   `CERT != MERGE AUTHORIZED`, `MODEL OUTPUT != AUTHORITY`,
   `executor self-verification != independent verification`.

## 3. Roles

| Role | Actor | Responsibility | May write (section 4) |
|---|---|---|---|
| Supervisor (orchestrator) | Fable or a dedicated supervisor session | Runs the loop, spawns subagents, gates packets, issues verdicts, runs audits, files level proposals; issues grants and merges to staging only where section 11 permits | `role_scopes.supervisor`. Never product code. |
| Executor subagent | Cursor Cloud session or Claude Code | One iteration: code, tests, lanes, reflection, next directive, packet | `allowed_scopes` plus `level_gated_scopes` |
| Verifier subagent | Fresh session given the head SHA only; reads the packet only after committing its cert | Runs both lanes on the exact head (CI, or the section 4.4 local fallback) and certifies pass or fail | `autonomy/certs/C-<n>.md` and its CI re-certification `C-<n>-ci.md` only |
| Instrument subagent | Fresh session | Reviews `[instrument]` commits for rigor loss and runs the drift check | `autonomy/drift/**` only |
| Owner (governor) | B0LK13 | The section 2 invariant 7 powers; at levels 0 and 1 also grants and staging merges | Everything |

The supervisor never executes code changes itself. Each subagent receives the grant, the
directive, the policy hash, the base SHA and its role file under
`autonomy/instruments/skills/` (once one exists), and nothing else.

## 4. Machine-readable rules

The fenced block below is the single source `autonomy/tools/preflight.py` reads. If prose and
block ever disagree, the stricter reading wins and the iteration stops with
`OWNER_DECISION_REQUIRED`.

```yaml
# autonomy-policy v1
autonomy_level: 0
allowed_scopes:
  - src/**
  - tests/**
  - WORKLOG.md
  - docs/backlog.md
  - autonomy/directives/**
  - autonomy/packets/**
  - autonomy/ledger.jsonl
level_gated_scopes:
  1:
    - autonomy/instruments/skills/**
  2:
    - autonomy/instruments/directive-template.md
  3:
    - autonomy/instruments/verify-checklist.md
role_scopes:
  verifier:
    0:
      - autonomy/certs/C-{n}.md
      - autonomy/certs/C-{n}-ci.md
  instrument:
    0:
      - autonomy/drift/**
  supervisor:
    0:
      - autonomy/verdicts/**
      - autonomy/packets/**
      - autonomy/ledger.jsonl
      - autonomy/audits/**
      - autonomy/proposals/**
    2:
      - autonomy/grants/**
forbidden_scopes:
  - autonomy/policy.md
  - autonomy/loop.yaml
  - autonomy/tools/**
  - autonomy/grants/**
  - autonomy/verdicts/**
  - autonomy/certs/**
  - autonomy/drift/**
  - autonomy/audits/**
  - autonomy/proposals/**
  - .github/**
  - pyproject.toml
  - AGENTS.md
  - CLAUDE.md
  - AGENT-BOOTSTRAP.md
  - GOVERNANCE.md
  - RELEASING.md
  - SECURITY.md
  - VERSIONING.md
  - .claude/**
  - .cursor/**
  - .atlas/**
  - .atlas-project.yaml
  - atlas-vault-documentation/**
  - deps/**
  - scripts/**
  - "**/.env"
  - "**/.env.*"
  - "**/*.pem"
  - "**/*.key"
  - "**/*.p12"
  - "**/id_rsa*"
budget:
  max_files_touched: 25
  max_diff_lines: 1000
  max_wall_clock_minutes: 180
  max_tokens: 3000000
require_signed_grants: false
lanes:
  required:
    linux: "quality (ubuntu-latest, 3.12, full)"
    windows-native: "quality (windows-latest, 3.12, windows)"
  fallback:
    when: ci_unavailable
    run_by: verifier
    host: "designated verification host: Windows native + WSL Linux"
    lane_mode: local
    expires: ci_available
test_count: non_decreasing
```

### 4.1 How a changed path is judged

Paths come from `git diff --no-renames <merge-base(grant_ref, HEAD)> HEAD` (a rename is a
delete plus an add, and both paths are judged), for the role named by
`preflight.py scope --role`. Rules apply in this order:

1. `autonomy/HALT` and `autonomy/HALT-REQUEST` may be **added** by any role. Modifying or
   deleting either is a violation.
2. Floor for every role, hard-coded in the tool: `autonomy/policy.md`, `autonomy/loop.yaml`,
   `autonomy/tools/**`, `.github/**`.
3. Executor:
   1. Executor floor, hard-coded: `autonomy/grants/**`, `autonomy/verdicts/**`,
      `autonomy/certs/**`, `autonomy/drift/**`, `autonomy/audits/**`,
      `autonomy/proposals/**`. No grant exception opens it.
   2. A path matching the grant's `scope_exceptions` is allowed.
   3. A path matching `forbidden_scopes` is a violation.
   4. A path must match `allowed_scopes`, or `level_gated_scopes` for a level at or below
      the current level. Anything else is a violation (allow-list, fail closed).
4. Verifier, instrument and supervisor: a path must match the role's `role_scopes` for a
   level at or below the current level (`{n}` is the iteration number) and must not match
   `src/**` or `tests/**` (hard-coded). `scope_exceptions` never apply to these roles.
5. `autonomy/ledger.jsonl` is append-only for every role: the head content must start with
   the base content byte for byte. Appended `resume` events are owner-only, and the executor
   may append only `packet` events.
6. Every commit in `merge-base..HEAD`, including merge commits, carries exactly one
   `Atlas-Role` trailer equal to the role being checked. A merge that introduces files
   without that trailer is fail-closed.

Glob semantics: `*` and `?` stay within one path segment, `**` spans segments, and `**/`
also matches zero segments.

The `lanes.required` values are the expected GitHub check names of the existing
`.github/workflows/ci.yml` matrix jobs. CI runs on `pull_request` for any base branch, so a
PR into `autonomy/staging` exercises both lanes. The names are unconfirmed until a CI run
actually starts; a mismatch is an owner policy edit, not an executor fix.

### 4.2 Budget

- `max_files_touched` and `max_diff_lines` (added plus deleted) are counted over the same
  diff for every role, including packet, directive, ledger and `WORKLOG.md`. The tool
  enforces them.
- `max_wall_clock_minutes` and `max_tokens` are self-reported in `budget_used` and checked
  by the supervisor. A subagent that exceeds any budget is stopped; the iteration is marked
  FAILED and counts against promotion evidence.
- A grant may override budget keys (the ACCELERATE lever). Only a grant raises a budget; a
  directive cannot. From level 2 a supervisor-issued grant may not exceed this block.

### 4.3 Tests

- The collected test count (`python -m pytest --collect-only -q --no-cov`) at head must be
  at least the count at the merge base.
- Deleting, skipping, `xfail`-ing or de-selecting an existing test requires explicit
  authorization in the granted directive, cited in the packet.

### 4.4 Lanes, certs and the local fallback

A verifier cert is `autonomy/certs/C-<n>.md`, checked by
`python autonomy/tools/preflight.py cert --iteration <n> [--head <sha>] [--require ci]`.

- `lane_mode: ci`: both `lanes.required` lanes are certified from GitHub Actions run URLs on
  `head_sha`.
- `lane_mode: local` is the fallback (`lanes.fallback`). It is allowed only while CI is
  unavailable, cited by an INFRA_RED run URL in `ci_unavailable_evidence`. The verifier
  subagent, never the executor, runs both lanes on the designated verification host: native
  Windows and WSL Linux. For each lane the cert records every command with its exit code and
  duration, plus a host fingerprint. A fallback cert declares `expires: ci_available`.
- Expiry: a fallback cert expires when CI returns. The next CI run re-certifies the same head
  in `autonomy/certs/C-<n>-ci.md` with `lane_mode: ci` and the same `head_sha`, and from then on
  only the CI cert counts. A re-certification of a different head, or one whose `result` is
  `FAIL`, leaves the iteration uncertified, and a head already promoted on the fallback cert is
  an immediate stop (section 12.1).
- Consistency: `result` is `PASS` exactly when every recorded exit code is 0, and a cert whose
  `result` is `FAIL` certifies nothing.
- Removing `lanes.fallback` from the section 4 block disables local certs entirely.

Cert format (quote `head_sha`, so YAML never reads an all-digit SHA as a number):

```markdown
---
cert: C-<n>
iteration: <n>
role: verifier
head_sha: "<40 hex>"
lane_mode: local                # or ci
result: PASS                    # PASS exactly when every exit below is 0
expires: ci_available           # local only
ci_unavailable_evidence: https://github.com/<owner>/<repo>/actions/runs/<id>   # local only
lanes:
  linux:
    run_url: https://github.com/<owner>/<repo>/actions/runs/<id>   # ci only
    host:                       # local only: host fingerprint
      hostname: <name>
      os: <uname -sr, or Windows edition and build>
      python: <python --version>
      git: <git --version>
    commands:
      - {cmd: "python -m ruff check .", exit: 0, duration_seconds: 21.4}
      - {cmd: "python -m mypy src", exit: 0, duration_seconds: 96.0}
      - {cmd: "python -m pytest", exit: 0, duration_seconds: 4210.8}
  windows-native:               # same shape as linux
    ...
---

Free-text notes. The verifier reads RP-<n> only after committing this file.
```

## 5. Grants

Grants live at `autonomy/grants/G-<n>.md`, committed to the grant ref (default
`origin/main`) by the owner, or from level 2 by the supervisor. The tool reads only the keys
below: other top-level keys are ignored, and budget keys other than the four section 4 keys
are a configuration error.

```markdown
---
grant: G-<n>
iteration: <n>
issued_by: <owner | supervisor>
policy_sha: <64 hex, output of preflight.py sha>
base_sha: <40 hex commit the iteration must contain>
directive: autonomy/directives/D-ATLAS-ITER-<n>.md
budget:                 # optional overrides of section 4 budget keys
  max_files_touched: 10
  max_diff_lines: 400
  max_wall_clock_minutes: 90
  max_tokens: 1500000
scope_exceptions: []    # optional globs for the executor; never opens a floor
---

Free-text scope notes.
```

A grant verifies only if all of these hold (`preflight.py preflight --iteration <n>`):

- neither `autonomy/HALT` nor `autonomy/HALT-REQUEST` exists, locally or on the grant ref;
- the grant file exists, `grant` is `G-<n>` and `iteration` is `<n>`;
- `policy_sha` in the grant equals `loop.yaml` `policy_sha`, and both equal the SHA-256 of
  the current `policy.md`;
- the grant file, `policy.md`, and the directive named by the grant are byte-identical to
  their versions on the grant ref (a locally edited grant, policy, or granted directive is
  void; proposing `D-<n+1>` remains in scope);
- `base_sha` is an ancestor of `HEAD`;
- the directive named by the grant exists and is a normalized path under
  `autonomy/directives/` (`..` is rejected; `.` and empty segments are stripped so
  the scope pin matches the canonical git path);
- the ledger passes section 8.1;
- if `require_signed_grants` is true, the latest commit touching the grant on the grant ref
  has a good signature (`%G? == G`);
- `loop.yaml` `max_iterations_per_grant` is `1`, unless the autonomy level is 3 or higher.

## 6. Iteration protocol (executor)

For iteration `n`:

1. **Ground.** `git fetch` the grant ref, then branch from the grant-ref commit that
   contains the grant. Read the directive and `autonomy/verdicts/V-<n-1>.md` (if any).
   Ignore chat memory. A stale `origin/main` is not a clean gate.
2. **Preflight.** `python autonomy/tools/preflight.py preflight --iteration <n>`. The tool
   also fetches a remote-tracking `--grant-ref` (including `refs/remotes/<remote>/<branch>`)
   and then judges `HALT` / `HALT-REQUEST` and the grant, policy, and granted-directive pins
   on the unambiguous remotes ref, so a local branch named `origin/main` cannot shadow the
   fetched tip. Scope also rejects edits to the granted directive; propose `D-<n+1>`
   instead. A non-zero exit stops the iteration with no code changes.
3. **Plan.** Write a plan of at most 10 lines at the top of the packet before touching code:
   target, files, tests to add, verification command per lane.
4. **Execute.** Branch `iter/<n>`. Stay inside the section 4 scopes. Stop at budget. Every
   commit message ends with the trailer `Atlas-Role: executor`.
5. **Verify (self).** Run both lanes per `autonomy/instruments/verify-checklist.md` and
   `python autonomy/tools/preflight.py scope --iteration <n> --role executor`. Record exact
   commands and exit codes. Every lane ends GREEN, FAILED, TIMEOUT or INFRA_RED (CI could not
   start or the runner failed). A packet is never emitted while a lane is still running, and
   INFRA_RED is escalated, never reported as green.
6. **Reflect.** Name the instrument that failed or slowed this iteration and the concrete
   edit that would fix it. If an instrument scope is open at the current level, apply the
   edit in its own commit whose subject starts with `[instrument]`. The instrument subagent
   signs it off in `autonomy/drift/` before the supervisor gates it. At level 0 no instrument
   is writable: record the edit in the packet with `status: proposed` and do not apply it.
7. **Propose next.** Write `autonomy/directives/D-ATLAS-ITER-<n+1>.md` from
   `autonomy/instruments/directive-template.md`, derived from repository state and citing
   file paths.
8. **Emit.** Write `autonomy/packets/RP-<n>.md` (section 7), append one `packet` ledger line
   (section 8), push `iter/<n>`, and open a PR **against `autonomy/staging`**. Never open a
   PR against `main`.

## 7. Return packet contract (`autonomy/packets/RP-<n>.md`)

```
iteration: n
role: executor
grant: G-n (policy_sha)
base_sha / head_sha
plan: (as written before execution)
changes: [{path, +/-, purpose}]
lanes:
  linux:   {cmd, exit, status: GREEN|FAILED|TIMEOUT|INFRA_RED, lane_mode: ci|local, run_url|cert}
  windows: {cmd, exit, status: GREEN|FAILED|TIMEOUT|INFRA_RED, lane_mode: ci|local, run_url|cert}
tests: before=N after=M
claims: each with evidence pointer (sha:path:line | run_url)
instrument_change: {status: applied|proposed, path, rationale, diff_summary}
next_directive: D-ATLAS-ITER-<n+1> (path)
budget_used: {files, lines, minutes, tokens}
unknowns: explicit list, no silent gaps
```

Executor lane runs are evidence of the command and exit code only. A lane counts as GREEN for
the gate only via a CI run URL on the packet's `head_sha` or, while CI is unavailable, via a
valid `lane_mode: local` verifier cert on that head (section 4.4).

## 8. Ledger (`autonomy/ledger.jsonl`)

Append-only, one JSON object per line, UTF-8, LF. Lines are never edited or removed.

| Event | Appended by | Required fields |
|---|---|---|
| `packet` | executor | `iteration`, `grant`, `policy_sha`, `base_sha`, `head_sha`, `lanes`, `tests`, `budget_used`, `packet` |
| `verdict` | supervisor (owner at levels 0-1 when committing to `main`) | `iteration` (integer), `verdict` (section 9), `head_sha`, `verdict_path` |
| `audit` | supervisor | `iteration`, `audit_path` |
| `proposal` | supervisor | `proposal_path`, `target_level` |
| `halt_request` | any role | `reason`, `evidence` |
| `resume` | owner only | `by`, `reason` |

```json
{"event": "packet", "iteration": 1, "grant": "G-1", "policy_sha": "<sha256>", "base_sha": "<sha>", "head_sha": "<sha>", "lanes": {"linux": {"exit": 0, "status": "GREEN", "run_url": "<url>"}, "windows-native": {"exit": 0, "status": "GREEN", "run_url": "<url>"}}, "tests": {"before": 0, "after": 0}, "budget_used": {"files": 0, "lines": 0, "minutes": 0, "tokens": 0}, "packet": "autonomy/packets/RP-1.md"}
{"event": "verdict", "iteration": 1, "verdict": "CONTINUE", "head_sha": "<sha>", "verdict_path": "autonomy/verdicts/V-1.md"}
```

### 8.1 Ledger rules enforced by preflight (hard-coded in the tool)

- Every line is a JSON object with an `event` name; `verdict` events carry an integer
  `iteration` and a section 9 verdict. Anything else fails preflight as suspected tampering.
- A `STOP` verdict stops the loop until a later owner `resume` event. Resume leaves
  iteration `n` closed and is the documented recovery that opens `n+1`.
- An iteration closed by `CONTINUE`, `ACCELERATE`, `DEFER` or `STOP` cannot be preflighted
  again. One whose latest verdict is `OWNER_DECISION_REQUIRED` is paused.
- Iteration `n > 1` requires a `CONTINUE`, `ACCELERATE` or `DEFER` verdict for `n-1`, or a
  `STOP` on `n-1` followed by an owner `resume` that has not been followed by another
  `STOP`.
- Retry cap: `REDESIGN` reworks the same grant at most 2 times. A third `REDESIGN` verdict
  for the same iteration fails preflight, and the supervisor creates `autonomy/HALT-REQUEST`.

## 9. Supervisor gate

Input: the packet `RP-<n>`, the verifier cert `C-<n>`, the drift report under
`autonomy/drift/`, and the live repository diff. Never the packet alone.

1. Cert: `preflight.py cert --iteration <n> --head <head_sha>` exits 0, and the cert was
   committed by a separate verifier session. A `lane_mode: local` cert counts only while CI is
   unavailable (section 4.4). A missing or forged cert is an immediate stop (section 12).
2. Scope compliance: re-run `preflight.py scope` for each role's branch.
3. Evidence integrity: every claim resolves, and every lane run URL is green on `head_sha`.
4. Test monotonicity: no deleted, skipped or de-selected tests without directive
   authorization.
5. Instrument change review: if the edit reduces future verification rigor (removes a check,
   lowers a threshold, widens a scope), the verdict is REDESIGN.
6. Next-directive sanity: grounded in the repository, scoped, budgeted, aligned with the
   brain-first roadmap (`docs/product/CODER-ALPHA-NORTH-STAR.md`).
7. Drift: compare cumulative instrument edits over the last 5 iterations and flag the loop if
   it is optimizing for passing its own checks rather than shipping brain capabilities.

| Verdict | Action at levels 0-1 | Action from level 2 |
|---|---|---|
| ACCELERATE | Owner may issue `G-<n+1>` with a raised budget | Supervisor merges `iter/<n>` to staging after the cert; issues `G-<n+1>` up to the policy cap |
| CONTINUE | Owner issues `G-<n+1>` at the same budget | Supervisor merges after the cert; issues `G-<n+1>` at the same budget |
| REDESIGN | Executor reworks iteration n under the same grant (section 8.1 retry cap) | Same |
| DEFER | Branch parked; owner rewrites the next directive | Branch parked; escalate |
| STOP | Owner writes `autonomy/HALT` | Supervisor creates `autonomy/HALT-REQUEST`; escalate |
| OWNER_DECISION_REQUIRED | Loop pauses until the owner responds | Same |

Verdicts are written to `autonomy/verdicts/V-<n>.md`. No verdict merges to `main`.

## 10. Promotion path

`iter/<n>` -> PR to `autonomy/staging` -> verifier cert `C-<n>` on both lanes (CI, or the section 4.4 fallback) -> merge to
`autonomy/staging` (owner at levels 0-1, supervisor from level 2) -> owner merges
`autonomy/staging` -> `main`. Instrument changes ride the same path. They take effect only for
iterations whose grant is issued against a grant ref that contains them.

## 11. Authority ladder

| Level | Grants issued by | Merges to staging | Loop-editable instruments | Evidence required to enter the level |
|---|---|---|---|---|
| 0 | Owner | Owner | none (edits are proposed in packets) | Scaffold merged |
| 1 | Owner | Owner | `instruments/skills/**` | 5 iterations, at least 4 CONTINUE or better, 0 scope violations |
| 2 | Supervisor, 1 iteration each, budget within section 4 | Supervisor, after the verifier cert | + `directive-template.md` | 10 iterations at level 1, drift clean, 0 unresolved verifier/supervisor disagreements |
| 3 | Supervisor, up to 3 iterations per grant | Supervisor | + `verify-checklist.md` | 20 iterations at level 2, verifier pass rate at least 90%, instrument-edit ratio below 30% |
| 4 | Supervisor, rolling grants | Supervisor; owner merges staging to `main` on schedule | All instruments; policy proposals | 40 iterations at level 3, one authentic external estate consuming Atlas brain APIs over real MCP, zero HALT events in the last 20 |

The level is `autonomy_level` in section 4. No loop role can change it. When the evidence for
the next level is met, the supervisor files `autonomy/proposals/P-LEVEL-<k>.md` citing ledger
lines and audits, and the owner decides.

This ladder supersedes the phase plan in D-ATLAS-RSI-GOVERNED-LOOP-001 section 8. That plan's
phase 3 instrument unlock is split between level 2 (directive template) and level 3 (verify
checklist), and multi-iteration grants move from phase 4 to level 3.

## 12. Stop and escalate

### 12.1 Immediate stop (create `autonomy/HALT-REQUEST`, pause)

Scope violation; policy hash mismatch; verifier cert forged or missing; ledger tampering; any
attempt to touch a floor path; retry cap exceeded (a third REDESIGN for one iteration).

### 12.2 Escalate only (`OWNER_DECISION_REQUIRED`)

Budget cap reached mid-iteration; lane infrastructure red (CI could not start or the runner
failed, as opposed to red code); directive unresolvable from repository state.

### 12.3 Mechanized so far

Enforced by `autonomy/tools/preflight.py`: kill switches, pin equality, grant identity on the
grant ref, per-role and per-level scope floors and allow-lists, `Atlas-Role` trailers, ledger
append-only and role-limited events, ledger tampering, iteration sequencing, the retry cap,
the file and line budget, and cert structure (section 4.4: lane mode, per-command exit code and
duration, host fingerprint, `result` consistency, fallback allowed by policy, CI
re-certification of the same head).

Not mechanized yet, so checked by the supervisor, and to be decided by the owner before level
2: cert-before-packet ordering and forgery detection, whether CI really was unavailable when a
fallback cert was written (the evidence URL is recorded, not queried), whether the fingerprinted
host really is the designated verification host, when CI has returned so a fallback cert has
expired, the verifier/supervisor disagreement
rule, escalation routing, the wall-clock and token budget kill, verification of
supervisor-issued grants against `autonomy/staging`, and the section 13 audit.

## 13. Five-iteration audit (supervisor)

Every 5 iterations the supervisor writes `autonomy/audits/A-<n>.md` and an `audit` ledger
event covering:

1. Verdict distribution and verifier/supervisor disagreement count.
2. Instrument-edit ratio and direction; flag any edit that removes a check, lowers a threshold
   or widens a scope.
3. Goodhart probe: a fresh verifier re-certifies one randomly chosen CONTINUE iteration, and
   the results are compared.
4. Brain-tier progress: iterations that shipped memory, provenance or governance capability
   versus loop plumbing. If plumbing exceeds 50% over 10 iterations, the supervisor issues
   REDESIGN of the directive template.
5. Cost versus cap.

## 14. Guardrails

- Budget caps are enforced by preflight and the scope gate, then checked again by the
  supervisor.
- Blast radius: no loop role writes to `main`, CI config, secrets, agent instruction files or
  this policy.
- Rollback: every iteration is one branch; revert means delete the branch.
- Anti-Goodhart: the drift check, the audit's Goodhart probe, and a verifier with no packet
  access until after certification. Gate code (`autonomy/tools/**`) is outside every
  loop-writable scope.

## 15. Metrics (derived from the ledger)

Iterations per week, acceptance rate, mean budget utilization, test delta, instrument-edit
ratio (instrument diff lines / total diff lines; should stay below 30%), verifier pass rate,
verdict distribution.

## 16. Changing this policy

Only the owner edits this file. In the same commit the owner updates `loop.yaml`
`policy_sha` to the new `preflight.py sha` output. Every outstanding grant against the old
hash becomes void. `tests/unit/test_autonomy_preflight.py` fails CI if `loop.yaml` and this
file drift apart.
