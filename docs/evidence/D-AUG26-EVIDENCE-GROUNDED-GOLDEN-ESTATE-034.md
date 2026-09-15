# D-034 — Evidence-Grounded Golden Estate Verification

Independent, reproducible verification of PR #608 (Golden Estate carrier) and investigation
of the SEC021 test failure surfaced under D-033. Every claim below is tagged with its
provenance class; see the companion JSON for full machine-readable detail.

**MERGE_AUTHORIZATION = NOT_GRANTED.** This is evidence, not a certification or an integration action.

## D-027 status

`D027_TRUST_STATUS = UNSUBSTANTIATED`. Searched exhaustively (all branches' commit messages,
full-text grep across every remote branch tree, GitHub PR/issue search) in both D-033 and D-034
sessions. Zero hits. No Golden Estate result in this document depends on D-027 being true.

## Live state (reconfirmed this session)

| Object | HEAD | Tree | Target moved? |
|---|---|---|---|
| main | `f6b2495a0319...` | `9c670d710ec6...` | — |
| #607 | `80dd9d01a38e...` | `0eab2f88b928...` | NO |
| #608 | `0987bf2af0a1...` | `2c37c950d27a035995cfb019edaeff871686ec3d` | NO |

## Agent A — Golden Estate semantic IV

Independently re-derived the expected file list from #516's own diff (not the implementation
commit's claim), then SHA-256'd every file individually.

- Expected ported files: **21** — Actual: **21**
- Missing: **0** — Extra: **0**
- Byte-identical: **21 / 21** — Semantically changed: **0**

## Agent B — CI semantic IV

Raw diff of `.github/workflows/ci.yml` between #607 and #608 heads: **1 insertion, 1 deletion**,
same line. Scanned every added line for `if:`, `paths`, `continue-on-error`, `permissions`,
`secrets`, `env:`, `matrix`, `needs:` — none present. All of `CI_TRIGGER_CHANGE`,
`CI_PERMISSION_CHANGE`, `CI_JOB_REMOVAL`, `CI_EXISTING_TEST_REMOVAL`, `CI_GATE_WEAKENING` = **NO**.

## Agent C — Adversarial review (bounded)

Manual inspection of `curator.py` confirms real defensive code: `_is_symlink_or_junction()`
checks both POSIX `S_ISLNK` and the Windows reparse-tag bit; `_escapes()` uses
`Path.resolve(strict=False)` with a proper `root not in resolved.parents` check. Carrier's own
adversarial + Windows-remediation test files execute clean. `NEW_VALID_P0 = 0`, `NEW_VALID_P1 = 0`.
This was a bounded, time-boxed pass — not a claim of exhaustive security audit.

## Agent D — SEC021 investigation (full root-cause analysis)

**Classification: D = ENVIRONMENT_ONLY_NON_PRODUCT_FAILURE**

- The failing test file and every dependency it imports are **byte-identical** across main, #607,
  and #608 (independently hashed) — this cannot be a regression from #608.
- Root cause: this specific interactive sandbox has a real, unrelated, currently-broken `mda` CLI
  tool installed via `pipx` at `~/.local/share/pipx/venvs/mda-cli/bin/mda` (symlinked onto PATH).
  Invoking it directly reproduces the exact failure: `ModuleNotFoundError: No module named
  'mda_cli.cli'`.
- The product code is working correctly: it discovers the PATH entry, attempts to use it, the
  invocation fails, and the product correctly categorizes this as `process-failed` — a real,
  valid category the test's assertion set (`{"unknown-contract", "executable-missing"}`) didn't
  anticipate.
- **The actual security invariant under test — `UNTRUSTED_REPOSITORY_CONFIG != EXECUTION_AUTHORITY`
  — is never violated**, in any state: the malicious payload's marker file is never created.
- Control: sanitizing `PATH` to `/usr/bin:/bin` makes the test (and the full
  `atlas-vault-documentation/tests` suite) pass 100% clean.
- Differential matrix: fails identically alone / module / suite / combined-invocation (not
  order-dependent); fully deterministic given PATH state (not flaky).
- **Not remediated** — there is no repository defect to fix; this will pass on any clean CI runner
  or developer machine that doesn't happen to have this specific broken local tool installed. A
  minor test-hermeticity improvement (explicit PATH sanitization in the test) is noted as optional
  future work, not applied here.

## Fresh Golden Estate certification (re-run this session, not reused from D-033)

- `GE_TESTS`: **24/24 passed**
- `SKILL_SCHEMA`: **2/2 passed**
- `SKILL_HASH`: recomputed, **matches**
- `RUFF_CONFIGURED_SCOPE`: **PASS** (this repo's `pyproject.toml` explicitly excludes
  `atlas-vault-documentation/` from ruff's `include`; that is the actual configured gate).
  Ad-hoc whole-tree check separately found 5 pre-existing style nits, all inherited verbatim
  from #516's own content — not conflated with the configured-scope result.
- `MYPY`: not applicable — same out-of-scope reasoning as ruff (`mypy_path = "src"`).

## Windows verification

No Windows execution capability is available to this session or any agent it can dispatch.
Rather than stop, a complete deterministic execution packet was prepared (exact commands,
environment requirements, pass/fail criteria, hash bindings to `0987bf2af0a1...` /
`2c37c950d27a035995cfb019edaeff871686ec3d`) — see the JSON's `windows_verification.execution_packet`.
`WINDOWS_VERIFICATION = LOCAL_WINDOWS_REQUIRED`.

## PR607 owner packet (no D-027 citation)

Base solely on verifiable facts: exact base/head/tree, 5 changed paths (all docs/evidence),
runtime/test/workflow delta = 0, 0 review threads, 0 P0/P1 found (non-exhaustive), mergeable,
and CI failures independently classified as external (GitHub Actions budget message, Bugbot
usage-limit message — both quoted verbatim from the platform, not inferred).

## PR608 retarget simulation

`git merge-tree` of PR607-head + PR608-head: **clean, 0 conflicts**, simulated tree
`2c37c950d27a035995cfb019edaeff871686ec3d`
(matches PR608's own tree — expected, since PR608's current base already equals PR607's head).

## 43-PR supersession drift

Sampled 5 of 43 (#536, #550, #565, #580, #592): **0 drift**, all heads match previously recorded
values exactly. Full list not re-audited per directive guidance (spend effort only where drift
is found).

## Successor DAG

| Node | Class |
|---|---|
| SEC021 investigation | ALREADY_COMPLETE |
| SEC021 test hermeticity improvement | READY (optional, not executed — fixes a non-bug) |
| PR607 owner review | BLOCKED_BY_OWNER |
| PR608 owner review / stacking decision | BLOCKED_BY_OWNER |
| PR608 retarget after #607 merges | DERIVABLE (simulation done, execution blocked on #607) |
| Windows-side D-034 packet execution | BLOCKED_EXTERNAL |
| 43-PR supersession execution | BLOCKED_BY_OWNER |
| D-027 evidence archaeology | ALREADY_COMPLETE (exhaustive, twice, zero hits) |

`READY = 1, DERIVABLE = 1, BLOCKED_BY_OWNER = 3, BLOCKED_EXTERNAL = 1, ALREADY_COMPLETE = 2, UNKNOWN_REQUIRES_AUDIT = 0`

MERGE_AUTHORIZATION = NOT_GRANTED.
