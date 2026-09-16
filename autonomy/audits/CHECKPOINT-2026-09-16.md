# Checkpoint 2026-09-16: PR #1 findings closed, loop rehearsed, owner unblock kit ready

Session end state for the Atlas executor at `autonomy_level 0`. Every line cites a SHA, a path
or a URL. Nothing here is a certification, a verdict or a merge.

## 1. What this session changed

Branch `autonomy/scaffold`, PR https://github.com/bolkdev/project-atlas/pull/1 (`-> main`).

- Session start head: `b6e0660265dda5a9a7dea0a9662651ef5072c67d`, CI green in
  https://github.com/bolkdev/project-atlas/actions/runs/35018874179 (all four jobs success).
- `311ce7b6991ddf18e6a39e682b4a3ee45da72b67`: closes the five open review findings.
- This commit: the four defects internal gating found in `311ce7b6` (below), the dry-run report,
  the owner unblock kit and this checkpoint.

## 2. The five review findings, now closed

| Finding | Fix | Evidence |
|---|---|---|
| Codex P1 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318109 | Preflight refreshes the grant ref before reading it, and fails closed when the fetch fails | `autonomy/tools/preflight.py` `refresh_grant_ref`; `test_preflight_refreshes_the_grant_ref_before_reading_halt`, `test_preflight_fails_closed_when_the_grant_ref_cannot_be_refreshed` |
| Codex P1 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318117 | The granted directive is byte-compared with its grant-ref copy | `check_git_preflight`; `test_the_granted_directive_is_pinned_to_the_owner_ref` |
| Codex P2 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318123 | Appended ledger bytes must be UTF-8, LF-terminated, one valid record per line, no blank lines | `check_ledger_append`; `test_appended_ledger_bytes_must_satisfy_the_stored_contract`, `test_the_append_gate_accepts_exactly_what_load_ledger_accepts` |
| Bugbot `b3f1d16c-a6ae-46fd-a282-269eb5e1878d` https://github.com/B0LK13/project-atlas/pull/946#pullrequestreview-5214910083 | An owner `resume` lifts the `STOP` verdicts before it, so the stopped iteration can be re-run | `check_ledger`; `test_owner_resume_reopens_the_iteration_a_stop_closed`, `test_resume_lifts_only_the_stop_it_follows` |
| Required checks missing `compat` and `control-plane` | `lanes.required` names all four CI checks; `lanes.cert_lanes` names the two host lanes a cert covers | `autonomy/policy.md` section 4; `test_repo_policy_requires_every_ci_check_and_certifies_only_host_lanes` |

Each fix was checked against the previous head: the old gate has no `refresh_grant_ref`, never
compares the directive, accepted an unterminated and an invalid-UTF-8 append, left no legal step
after STOP plus resume, and rejects the four-check policy outright.

## 3. Defects internal gating found in my own fix, and closed

1. Supervisor, blocking: the first resume fix scoped every rule to post-resume events, so an
   unrelated `resume` erased the retry cap and reopened closed or paused iterations. Now a resume
   lifts only prior `STOP` verdicts.
2. Supervisor, blocking: `--no-fetch` was an unrestricted HALT bypass on the gate. The CLI flag is
   removed; `fetch=False` remains only as an in-process parameter.
3. Supervisor, non-blocking: the green status of the four required checks is not mechanized here.
   Disclosed in policy section 12.3.
4. Verifier: an interior blank line passed the append gate but locked out the stored-ledger
   reader. Now refused at the gate, with a parity test over both contracts.

Advisory only. Neither subagent wrote to the repository, and neither verdict is owner closure:
the supervisor returned REDESIGN on `311ce7b6`, and the verifier returned NOT_CERTIFIED because
CI had not finished within its budget.

## 4. Verification at this head

- `python -m ruff check .` exit 0; `python -m mypy --strict --ignore-missing-imports
  autonomy/tools/preflight.py` exit 0.
- `PYTHONPATH=src python -m pytest tests/unit/test_autonomy_preflight.py --no-cov` 107 passed
  (85 at session start).
- `python autonomy/tools/preflight.py sha` equals `autonomy/loop.yaml` `policy_sha`
  `a54037f251d3caf77c86a18cef13f69280600b135629a8aa8a0501787c34b94f`.
- `python autonomy/tools/preflight.py preflight --iteration 1` exits 1 with exactly
  `missing grant autonomy/grants/G-1.md`.
- Dry run: 14 of 14 rehearsal steps as required, `autonomy/packets/DRYRUN-2026-09-16.md`.
- CI for this commit's head is a new run on branch `autonomy/scaffold`; check
  `gh run list --repo bolkdev/project-atlas --branch autonomy/scaffold --limit 1`.

## 5. Owner-gated, nothing else blocks iteration 1

Full instructions and the exact file contents: `autonomy/packets/OWNER-UNBLOCK-KIT-2026-09-16.md`.

1. Merge PR #1 after CI is green on the final head and an independent verifier certifies it.
2. `git branch autonomy/staging origin/main && git push -u origin autonomy/staging`.
3. Commit `autonomy/grants/G-1.md` and `autonomy/directives/D-ATLAS-ITER-1.md` to `main`, with
   `base_sha` set to the merge commit and `policy_sha` exactly as the kit states.
4. Delete https://github.com/bolkdev/project-atlas-1; rotate the PAT.
5. Decide: the two fallback-lane rules (pin `origin/main` in the verifier's clone; how
   `product_perf` timing under coverage is treated), and whether
   `autonomy/instruments/skills/**` opens at level 0 or stays at level 1.

## 6. Scope note

`autonomy/audits/**` is an executor-forbidden scope (policy section 4.1), so
`preflight.py scope --role executor` flags this file, as it flagged
`SHUTDOWN-2026-09-15.md`. It exists because the owner's directive required a checkpoint. The
owner should either accept the exception or move checkpoints under a scope the executor holds.
`autonomy/packets/**` is an executor scope, so the dry-run report and the unblock kit are clean.

## 7. Resume instructions

Read `autonomy/policy.md`, then this file, then the unblock kit. Run
`python autonomy/tools/preflight.py preflight --iteration 1`: until the owner commits `G-1`, it
must fail with exactly `missing grant`. Do not start iteration work, edit
`autonomy/tools/**` or `autonomy/policy.md`, or push to the `old` remote.
