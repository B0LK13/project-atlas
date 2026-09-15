# Verify checklist (executor self-verification)

Instrument: loop-improvable from policy phase 3 (`autonomy/policy.md` section 4).
An edit that reduces verification rigor is a REDESIGN verdict (policy section 9, check 4).

Run every step from the iteration worktree on branch `iter/<n>`. Record each command
verbatim with its exit code in the packet. Never summarize a command as "passed".

## 0. Before code

- [ ] `python autonomy/tools/preflight.py preflight --iteration <n>` exits 0.
- [ ] Baseline test count at the merge base: check out
      `git merge-base origin/main HEAD` detached, run
      `python -m pytest --collect-only -q --no-cov`, record the final count line, return.
- [ ] `python -c "import project_atlas; print(project_atlas.__file__)"` resolves to this
      worktree's `src/` (otherwise run with `PYTHONPATH=src`). An editable install from
      another checkout silently tests the wrong code.

## 1. Linux lane (CI gate: `quality (ubuntu-latest, 3.12, full)`)

- [ ] `python -m ruff check .`
- [ ] `python -m mypy src`
- [ ] `python -m pytest`
- [ ] CI run URL for `head_sha` recorded and green.

## 2. Native Windows lane (CI gate: `quality (windows-latest, 3.12, windows)`)

- [ ] `python -m pytest -m product_perf --no-cov`
- [ ] `python -m pytest -m "not product_perf"`
- [ ] New CLI or tool output is encodable on cp1252 (prefer ASCII-only messages).
- [ ] CI run URL for `head_sha` recorded and green.
- [ ] A local native Windows run is recorded as local evidence only; it never
      substitutes for the CI run URL.

## 3. Scope, tests and budget

- [ ] All work committed; `python autonomy/tools/preflight.py scope --iteration <n>` exits 0.
- [ ] Head test count `>=` baseline; any removed or skipped test cites directive authorization.
- [ ] `budget_used` filled from `git diff --shortstat $(git merge-base origin/main HEAD) HEAD`.

## 4. Evidence

- [ ] Every packet claim carries `sha:path:line` or a run URL. No pointer, no claim.
- [ ] Unknowns listed explicitly, including anything left unverified.
