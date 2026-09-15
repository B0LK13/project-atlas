# Verify checklist (executor self-verification)

Instrument: loop-editable from autonomy level 3 (`autonomy/policy.md` sections 4 and 11).
An edit that reduces verification rigor is a REDESIGN verdict (policy section 9, check 5).

Run every step from the iteration worktree on branch `iter/<n>`. Record each command
verbatim with its exit code in the packet. Never summarize a command as "passed".
Every lane ends GREEN, FAILED, TIMEOUT or INFRA_RED; never emit a packet with a lane running.

## 0. Before code

- [ ] `python autonomy/tools/preflight.py preflight --iteration <n>` exits 0 (kill switches,
      pins, grant on the grant ref, ledger rules and retry cap).
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
- [ ] CI run URL for `head_sha` recorded and green, or, while CI is unavailable, a verifier
      fallback cert (policy section 4.4) covering this lane.

## 2. Native Windows lane (CI gate: `quality (windows-latest, 3.12, windows)`)

- [ ] `python -m pytest -m product_perf --no-cov`
- [ ] `python -m pytest -m "not product_perf"`
- [ ] New CLI or tool output is encodable on cp1252 (prefer ASCII-only messages).
- [ ] CI run URL for `head_sha` recorded and green, or, while CI is unavailable, a verifier
      fallback cert (policy section 4.4) covering this lane.
- [ ] An executor's own local run is recorded as local evidence only; it never substitutes
      for the CI run URL or the verifier's fallback cert.

## 2a. Fallback lanes (verifier only, while CI is unavailable)

- [ ] Cite the INFRA_RED run URL that shows CI could not run.
- [ ] Run both lanes on the designated verification host (native Windows and WSL Linux) on the
      exact `head_sha`, from a clean checkout of that commit.
- [ ] Record every command, exit code, `duration_seconds` and the host fingerprint per lane in
      `autonomy/certs/C-<n>.md` with `lane_mode: local` and `expires: ci_available`.
- [ ] `python autonomy/tools/preflight.py cert --iteration <n> --head <head_sha>` exits 0.
- [ ] When CI returns, re-certify the same head in `autonomy/certs/C-<n>-ci.md`.

## 3. Scope, tests and budget

- [ ] Every commit message ends with the trailer `Atlas-Role: executor`.
- [ ] All work committed;
      `python autonomy/tools/preflight.py scope --iteration <n> --role executor` exits 0.
- [ ] CI that could not start (billing, runner outage) is INFRA_RED: escalate, never green.
- [ ] Head test count `>=` baseline; any removed or skipped test cites directive authorization.
- [ ] `budget_used` filled from `git diff --shortstat $(git merge-base origin/main HEAD) HEAD`.

## 4. Evidence

- [ ] Every packet claim carries `sha:path:line` or a run URL. No pointer, no claim.
- [ ] Unknowns listed explicitly, including anything left unverified.
