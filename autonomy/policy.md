# Autonomy Policy: Governed RSI Loop

- Decision: `D-ATLAS-RSI-GOVERNED-LOOP-001`
- Status: **DRAFT**, proposed by the executor on branch `autonomy/scaffold`. It becomes
  binding when the owner merges it. From then on only the owner edits this file.
- Pin: `policy_sha` = SHA-256 of this file's exact LF bytes
  (`python autonomy/tools/preflight.py sha`). The pin is recorded in `autonomy/loop.yaml`
  and in every grant. A grant whose `policy_sha` differs from the current file is void.

## 1. Purpose and boundary

A bounded recursive self-improvement loop: an executor agent develops Atlas one
iteration at a time, with a supervisor gate and an owner grant between iterations.
This is the "factory" tier dogfooding the "brain". It is not Strategy C.

The loop **may improve its own instruments** (directives, checklists, tests, skills).
It **may never improve its own authority** (this policy, `loop.yaml`, grants, verdicts,
the preflight tool, CI, release workflows, secrets, agent instruction files).

## 2. Invariants

1. Repository truth over conversation memory. An iteration reads the grant, directive
   and prior verdict from the repository and ignores chat memory.
2. The executor never merges to `main` or `autonomy/staging`. The supervisor never
   merges. Only the owner, or a merge agent the owner separately authorizes, merges.
3. Every claim in a return packet cites a commit SHA, a file path (optionally `:line`),
   or a CI run URL. A claim without an evidence pointer is an automatic REJECT.
4. Kill switch: if `autonomy/HALT` exists (in the working tree or on the grant ref) the
   loop stops before its next step. Any role may create `HALT`; only the owner removes it.
5. Autonomy is granted per iteration by a verifiable grant, never standing. No valid
   grant means no iteration.
6. Truth boundaries hold: `PROMOTE_ELIGIBLE != MERGED`, `CONTINUE != MERGE AUTHORIZED`,
   `MODEL OUTPUT != AUTHORITY`, `executor self-verification != independent verification`.

## 3. Roles

| Role | Actor | Owns | May write |
|---|---|---|---|
| Executor | Main agent (Cursor Cloud session or Claude Code) | Directive execution, verification lanes, return packet | Section 4 allowed scopes on `iter/<n>` |
| Supervisor | Fable (adversarial, advisory) | Gate audit of packet vs live repository | Nothing in the repo; returns verdict text |
| Governor | Owner | Grants, merges, this policy, `loop.yaml`, `HALT` removal, verdict commits | Everything |
| Independent Verifier | Separate agent session, fresh context, no packet access before certifying | Certification of the final head on Linux and native Windows | Certification report only |

## 4. Machine-readable rules

The fenced block below is the single source `autonomy/tools/preflight.py` reads. If
prose and block ever disagree, the stricter reading wins and the iteration stops with
`OWNER_DECISION_REQUIRED`.

```yaml
# autonomy-policy v1
phase: 0
allowed_scopes:
  - src/**
  - tests/**
  - WORKLOG.md
  - docs/backlog.md
  - autonomy/directives/**
  - autonomy/packets/**
  - autonomy/ledger.jsonl
  - autonomy/instruments/skills/**
phase_gated_scopes:
  3:
    - autonomy/instruments/verify-checklist.md
    - autonomy/instruments/directive-template.md
forbidden_scopes:
  - autonomy/policy.md
  - autonomy/loop.yaml
  - autonomy/grants/**
  - autonomy/verdicts/**
  - autonomy/tools/**
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
required_lanes:
  linux: "quality (ubuntu-latest, 3.12, full)"
  windows-native: "quality (windows-latest, 3.12, windows)"
test_count: non_decreasing
```

### 4.1 How a changed path is judged

Paths come from `git diff --no-renames <merge-base(grant_ref, HEAD)> HEAD` (a rename is
a delete plus an add, and both paths are judged). Rules apply in this order:

1. `autonomy/HALT` may be **added**. Modifying or deleting it is a violation.
2. Never-grantable floor: `autonomy/policy.md`, `autonomy/loop.yaml`,
   `autonomy/grants/**`, `autonomy/verdicts/**`, `autonomy/tools/**`, `.github/**`.
   This is hard-coded in the tool, and no grant exception can open it.
3. A path matching the grant's `scope_exceptions` is allowed.
4. A path matching `forbidden_scopes` is a violation.
5. A path must match `allowed_scopes`, or `phase_gated_scopes` for a phase `<=` the
   current `phase`. Anything else is a violation (allow-list, fail closed).
6. `autonomy/ledger.jsonl` is append-only: the head content must start with the base
   content byte for byte.

Glob semantics: `*` and `?` stay within one path segment, `**` spans segments, and
`**/` also matches zero segments.

The `required_lanes` values are the expected GitHub check names of the existing
`.github/workflows/ci.yml` matrix jobs. CI runs on `pull_request` for any base branch,
so a PR into `autonomy/staging` exercises both lanes. Confirm the exact check names on
the first staging PR; a mismatch is an owner policy edit, not an executor fix.

### 4.2 Budget

- `max_files_touched` and `max_diff_lines` (added plus deleted) are counted over the
  same diff, including packet, directive, ledger and `WORKLOG.md`. The tool enforces them.
- `max_wall_clock_minutes` and `max_tokens` are self-reported in the packet's
  `budget_used` and checked by the supervisor.
- A grant may override budget keys (the owner's ACCELERATE lever). Only the grant can
  raise a budget; a directive cannot.
- On reaching any budget, the executor stops, verifies what exists and emits the packet
  with the unfinished remainder listed under `unknowns`.

### 4.3 Tests

- The collected test count (`python -m pytest --collect-only -q --no-cov`) at head must be
  `>=` the count at the merge base.
- Deleting, skipping, `xfail`-ing or de-selecting an existing test requires explicit
  authorization in the directive the owner granted, cited in the packet.

## 5. Grants

Grants are owner-authored: `autonomy/grants/G-<n>.md`, committed by the owner to the
grant ref (default `origin/main`). Format:

```markdown
---
grant: G-<n>
iteration: <n>
issued_by: owner
policy_sha: <64 hex, output of preflight.py sha>
base_sha: <40 hex main commit the iteration must contain>
directive: autonomy/directives/D-ATLAS-ITER-<n>.md
budget:                 # optional overrides of section 4 budget keys
  max_diff_lines: 1500
scope_exceptions: []    # optional globs; never opens the section 4.1 floor
---

Free-text scope notes from the owner.
```

A grant verifies only if all of these hold (`preflight.py preflight --iteration <n>`):

- `autonomy/HALT` is absent;
- the grant file exists, `grant` is `G-<n>`, `iteration` is `<n>`;
- `policy_sha` in the grant equals `loop.yaml` `policy_sha`, and both equal the SHA-256
  of the current `policy.md`;
- the grant file and `policy.md` are byte-identical to their versions on the grant ref
  (a locally edited grant or policy is void);
- `base_sha` is an ancestor of `HEAD`;
- the directive file named by the grant exists;
- if `require_signed_grants` is true, the latest commit touching the grant on the grant
  ref has a good signature (`%G? == G`);
- `loop.yaml` `max_iterations_per_grant` is `1`, unless `phase >= 4`.

## 6. Iteration protocol (executor)

For iteration `n`:

1. **Preflight.** `python autonomy/tools/preflight.py preflight --iteration <n>`. A
   non-zero exit stops the iteration with no code changes.
2. **Ground.** `git fetch`, branch from the grant ref commit containing the grant, read
   the directive and `autonomy/verdicts/V-<n-1>.md` (if any). Ignore chat memory.
3. **Plan.** Write a plan of at most 10 lines at the top of the packet before touching
   code: target, files, tests to add, verification command per lane.
4. **Execute.** Branch `iter/<n>`. Stay inside the section 4 scopes. Stop at budget.
5. **Verify (self).** Run both lanes per `autonomy/instruments/verify-checklist.md`, and
   `python autonomy/tools/preflight.py scope --iteration <n>`. Record exact commands and
   exit codes.
6. **Reflect.** Name the instrument that failed or slowed this iteration. Apply one
   concrete edit within the instrument scopes open at the current phase, in its own commit
   whose subject starts with `[instrument]`.
7. **Propose next.** Write `autonomy/directives/D-ATLAS-ITER-<n+1>.md` from
   `autonomy/instruments/directive-template.md`, derived from repository state and citing
   file paths.
8. **Emit.** Write `autonomy/packets/RP-<n>.md` (section 7), append one `packet` ledger
   line (section 8), push `iter/<n>`, and open a PR **against `autonomy/staging`**. Never
   open a PR against `main`.

## 7. Return packet contract (`autonomy/packets/RP-<n>.md`)

```
iteration: n
grant: G-n (policy_sha)
base_sha / head_sha
plan: (as written before execution)
changes: [{path, +/-, purpose}]
lanes:
  linux:   {cmd, exit, run_url}
  windows: {cmd, exit, run_url}
tests: before=N after=M
claims: each with evidence pointer (sha:path:line | run_url)
instrument_change: {path, rationale, diff_summary}
next_directive: D-ATLAS-ITER-<n+1> (path)
budget_used: {files, lines, minutes, tokens}
unknowns: explicit list, no silent gaps
```

Local lane runs are evidence of the command and exit code only. A lane counts as green
for the gate only via a CI run URL on the packet's `head_sha`.

## 8. Ledger (`autonomy/ledger.jsonl`)

Append-only, one JSON object per line, UTF-8, LF. Lines are never edited or removed.

```json
{"event": "packet", "iteration": 1, "grant": "G-1", "policy_sha": "<sha256>", "base_sha": "<sha>", "head_sha": "<sha>", "lanes": {"linux": {"exit": 0, "run_url": "<url>"}, "windows-native": {"exit": 0, "run_url": "<url>"}}, "tests": {"before": 0, "after": 0}, "budget_used": {"files": 0, "lines": 0, "minutes": 0, "tokens": 0}, "packet": "autonomy/packets/RP-1.md"}
{"event": "verdict", "iteration": 1, "verdict": "CONTINUE", "head_sha": "<sha>", "verdict_path": "autonomy/verdicts/V-1.md"}
```

The executor appends `packet` lines. The owner appends `verdict` lines when committing
the supervisor's verdict to `autonomy/verdicts/V-<n>.md`.

## 9. Supervisor gate

Input: the packet **and** the live repository diff, never the packet alone.

1. Scope compliance: the diff touches only section 4 scopes (re-run the `scope` command).
2. Evidence integrity: every claim resolves, and every lane run URL is green on `head_sha`.
3. Test monotonicity: no deleted, skipped or de-selected tests without directive
   authorization.
4. Instrument change review: if the edit reduces future verification rigor, the verdict
   is REDESIGN.
5. Next-directive sanity: grounded in the repository, scoped, budgeted, aligned with the
   brain-first roadmap (`docs/product/CODER-ALPHA-NORTH-STAR.md`).
6. Drift: compare cumulative instrument edits over the last 5 iterations and flag the loop
   if it is optimizing for passing its own checks rather than shipping brain capabilities.

| Verdict | Action |
|---|---|
| ACCELERATE | Owner may issue `G-<n+1>` with a raised budget |
| CONTINUE | Owner issues `G-<n+1>` at the same budget |
| REDESIGN | Executor reworks iteration n; no new grant |
| DEFER | Branch parked; owner rewrites the next directive |
| STOP | Owner writes `autonomy/HALT` |
| OWNER_DECISION_REQUIRED | Loop pauses until the owner responds |

## 10. Promotion path

`iter/<n>` -> PR to `autonomy/staging` -> Independent Verifier (fresh session, no packet
access until after certification) certifies the head on both lanes -> owner merges
`autonomy/staging` -> `main`. Instrument changes ride the same path. They take effect only
for iterations whose grant is issued against a grant ref that contains them.

## 11. Phases

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0 | Scaffold, empty ledger, `G-1` issued | Files present, `policy_sha` pinned |
| 1 | One manual iteration end to end | Packet passes the gate with CONTINUE |
| 2 | Five consecutive iterations, one grant each | At least 4 of 5 CONTINUE or better, zero scope violations |
| 3 | Executor may edit `directive-template.md` and `verify-checklist.md` | Supervisor drift check clean over 5 iterations |
| 4 | Multi-iteration grants (`max_iterations_per_grant: 3`) | Only by explicit owner decision after ledger review |

The current phase is `phase` in section 4. Advancing it is a policy edit, so owner only.

## 12. Guardrails

- Budget caps are enforced by executor preflight and scope gate, then checked again by the
  supervisor.
- Blast radius: no agent writes to `main`, CI config, secrets, agent instruction files or
  this policy.
- Rollback: every iteration is one branch; revert means delete the branch.
- Anti-Goodhart: the supervisor drift check, plus an independent verifier with no packet
  access until after certification. Gate code (`autonomy/tools/**`) is outside every
  agent-writable scope.
- The cost ledger is reviewed by the owner every 5 iterations.

## 13. Metrics (derived from the ledger)

Iterations per week, acceptance rate, mean budget utilization, test delta,
instrument-edit ratio (instrument diff lines / total diff lines; should stay below 30%),
verdict distribution.

## 14. Changing this policy

Only the owner edits this file. In the same commit the owner updates `loop.yaml`
`policy_sha` to the new `preflight.py sha` output. Every outstanding grant against the old
hash becomes void. `tests/unit/test_autonomy_preflight.py` fails CI if `loop.yaml` and
this file drift apart.
