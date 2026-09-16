# Owner unblock kit, 2026-09-16

Everything the owner needs to start iteration 1. Four steps, in order. The executor cannot do
any of them: merging, grants and directives on `main` are owner-held (policy sections 2 and 3).

Current state: branch `autonomy/scaffold`, PR https://github.com/WezzSide/project-atlas/pull/1001.
For the head, run `git rev-parse origin/autonomy/scaffold`.

## Reconciliation note (D-ATLAS-SCAFFOLD-RECONCILE-001, 2026-09-16)

Both remotes fixed the same Codex/Bugbot findings independently. This branch is origin's six
commits (`7ace1fe0..84209842`) with the fork's four (`b6e06602..a134ef0b`) cherry-picked on top;
every conflict was resolved to the stricter, fail-closed side.

1. KEPT origin's `refresh_grant_ref`: it returns `refs/remotes/<remote>/<branch>`, so a local
   branch named `origin/main` cannot shadow the fetched tip, and a missing remote is fail-closed
   instead of being read as a local branch. DROPPED the fork's simpler version, which returned
   problems rather than raising and could be read through an ambiguous ref.
2. KEPT origin's resume rule: `STOP` leaves iteration `n` closed and the owner `resume` opens
   `n+1`. DROPPED the fork's rule, which re-opened `n` itself; an iteration closed by any verdict
   must stay closed (policy section 8.1), so origin's reading is the stricter one.
3. KEPT origin's role-trailer check over merge commits (no `--no-merges`), its scope-time
   grant-ref refresh, and its normalized-directive-path check (`..`, `\`, `.` segments rejected).
4. KEPT the fork's four `lanes.required` checks plus `lanes.cert_lanes`, its shared
   `_parse_ledger_line` (so an appended `verdict` record is validated exactly as the stored one
   is), and its policy section 12.3 disclosure that required-check *status* is not mechanized.
5. DROPPED the fork's `--no-fetch` CLI flag entirely; origin never had it, and a gate with a
   HALT-blind mode is not a gate. No behavior present on either side was weakened or removed.

The pin below is `policy_sha`
`a4e9c18c5821ae0e9f85bf9d83b46923f5d295d13e7cc02077e5ec2aee2f0399`, the value in
`autonomy/loop.yaml` as of this file's commit. **Re-check it before you commit the grant**:
after merging, run `python autonomy/tools/preflight.py sha` on `main`. It changes whenever
`policy.md` changes by even one byte, and a grant carrying the wrong value is void. If the two
differ, use the value the command prints, not the one written here.

## Step 1: merge PR #1001

Merge only after CI is green on the final head and an independent verifier has certified it.
The merge commit becomes the grant ref for `G-1`.

## Step 2: create the staging branch

```
git fetch origin
git branch autonomy/staging origin/main
git push -u origin autonomy/staging
```

Iteration PRs target `autonomy/staging`, never `main` (policy section 10).

## Step 3: commit the grant and the directive to `main`

Both files go on `main` in one commit. Replace `<MAIN_HEAD_AFTER_MERGE>` with the merge commit
SHA (`git rev-parse origin/main`), and set `policy_sha` to the output of
`python autonomy/tools/preflight.py sha` run on that merge commit. The value below is correct as
of this file's commit; confirm it rather than trusting it, because a grant whose `policy_sha`
does not match the policy byte-for-byte is void.

`autonomy/grants/G-1.md`:

```markdown
---
grant: G-1
iteration: 1
issued_by: owner
policy_sha: a4e9c18c5821ae0e9f85bf9d83b46923f5d295d13e7cc02077e5ec2aee2f0399
base_sha: <MAIN_HEAD_AFTER_MERGE>
directive: autonomy/directives/D-ATLAS-ITER-1.md
budget:
  max_files_touched: 10
  max_diff_lines: 400
  max_wall_clock_minutes: 90
  max_tokens: 1500000
scope_exceptions: []
---

Iteration 1 at autonomy level 0. Branch `iter/1`, PR into `autonomy/staging`.
Budget per the supervisor's V-0 finding 4. No instrument is writable at level 0: the
reflection step records its proposed edit in the packet.
```

`autonomy/directives/D-ATLAS-ITER-1.md`: the full text is in section "Directive" below.

Then check the grant from a clean clone:

```
python autonomy/tools/preflight.py preflight --iteration 1     # expect exit 0, PASS
```

If it still prints `missing grant`, the commit did not reach `origin/main`.

## Step 4: hand iteration 1 to an executor session

Give it the grant path and nothing else. It reads the directive, policy and base SHA from the
repository (policy section 6).

## Directive

```markdown
# D-ATLAS-ITER-1: Make the F6 cleanup-logging evidence test hold under the declared pytest floor

- Iteration: `1`
- Proposed by: executor (owner commits it)
- Derived from: the merged head of PR #1001 (`git rev-parse origin/main` after the merge)
- Roadmap anchor: `docs/backlog.md` AS-OBSIDIAN-CAPTURE-001. This is test rigor for a capture
  and provenance guarantee, not a new brain capability. Replace it if you prefer a capability target.

## Problem (repository truth)

- `tests/unit/test_as_obsidian_capture_001_f6_error_boundary.py:354` asserts on `caplog.records`
  for logger `project_atlas.obsidian_projection`.
- `src/project_atlas/logging.py:103` sets `propagate = False`, so those records reach pytest's
  capture handler only when `caplog.at_level(..., logger=...)` attaches a handler to that logger.
- `pyproject.toml` declares `pytest>=8.0` for dev.
- Measured 2026-09-15 on native Windows 11, Python 3.12.10, same code, clean venv: pytest 9.1.1
  PASSED, pytest 8.3.3 FAILED ("the swallowed cleanup failure was not logged at all"). CI passes
  because it installs current pytest: https://github.com/bolkdev/project-atlas/actions/runs/35018874179.
- So the guarantee holds only above the declared floor.

## Target

The F6 logging guarantee is asserted identically on every pytest version the project declares,
without weakening it: the test must still fail when the warning is missing or lacks `context`
with the path and the error.

## Scope

- Files expected to change: `tests/unit/test_as_obsidian_capture_001_f6_error_boundary.py`,
  `WORKLOG.md`, `autonomy/packets/RP-1.md`, `autonomy/ledger.jsonl`,
  `autonomy/directives/D-ATLAS-ITER-2.md`.
- Tests to add: a negative control proving the rewritten assertion still fails when the warning
  call is removed and when its `context` payload is dropped, restoring the file byte-identically.
- Out of scope: `src/**` behaviour changes; raising the pytest floor (`pyproject.toml` is
  forbidden; if the owner prefers that fix, the grant needs `scope_exceptions: [pyproject.toml]`).
- Test removals or skips authorized: `none`.

## Acceptance

- The F6 test passes under pytest 8.3.3 and 9.1.1 on native Windows, and on the CI Linux lane.
- The negative control fails with the warning removed, and with `context` removed.
- All four `lanes.required` checks green on the head.
- Test count at or above the merge-base count.

## Budget estimate

`files <= 6`, `diff lines <= 250`, `minutes <= 60`. Fits G-1.

## Risks and unknowns

- Other `caplog`-based tests may share the dependency. Grep and list them under `unknowns`;
  do not fix them in this iteration.
- The fallback Linux lane on the designated host cannot reproduce `product_perf` timing under
  coverage (open owner decision, policy section 12.3).
```

## Also owner-held, not blocking iteration 1

- Delete the stray fork https://github.com/bolkdev/project-atlas-1 (created 2026-09-15T19:56:18Z).
- Rotate the PAT (per D-ATLAS-SHUTDOWN-CHECKPOINT-001).
- Decide the two fallback-lane rules: pin `origin/main` in the verifier's clone, and how
  `product_perf` timing under coverage is treated.
- Decide whether `autonomy/instruments/skills/**` opens at level 0 or level 1. The policy
  currently opens it at level 1, the stricter reading (policy section 11).
