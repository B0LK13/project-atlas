# Checkpoint 2026-09-16: findings closed, branches reconciled, owner unblock kit ready

Session end state for the Atlas executor at `autonomy_level 0`. Every line cites a SHA, a path
or a URL. Nothing here is a certification, a verdict or a merge.

## 1. Reconciliation (D-ATLAS-SCAFFOLD-RECONCILE-001)

Canonical repository is now `WezzSide/project-atlas` (`origin`); `bolkdev/project-atlas` is
`fork`, read-only. `autonomy/scaffold` had diverged from the common base
`034a1264183b0814482cf73a679bab902480467d`:

- origin: six Cursor Agent commits `7ace1fe0..84209842`,
- fork: four executor commits `b6e06602..a134ef0b`,

both fixing the same Codex and Bugbot findings. This branch is origin's six with the fork's four
cherry-picked on top, every conflict resolved to the stricter, fail-closed side. The per-behavior
kept/dropped list is the reconciliation note in
`autonomy/packets/OWNER-UNBLOCK-KIT-2026-09-16.md`. Nothing was pushed to `fork`.

## 2. The findings, now closed on one branch

| Finding | Where it is fixed |
|---|---|
| Codex P1 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318109 (refresh the grant ref before reading HALT) | `refresh_grant_ref` fetches and returns `refs/remotes/<remote>/<branch>`; a missing remote raises rather than falling back to a local branch |
| Codex P1 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318117 (pin the granted directive) | `check_git_preflight` byte-compares grant, policy and granted directive; `load_grant` rejects non-normalized directive paths |
| Codex P2 https://github.com/B0LK13/project-atlas/pull/946#discussion_r4019318123 (validate appended ledger records) | `check_ledger_append` refuses non-UTF-8, CR, unterminated and blank lines, and validates each record with `_parse_ledger_line`, the same parser `load_ledger` uses |
| Bugbot `b3f1d16c-a6ae-46fd-a282-269eb5e1878d` | `check_ledger`: STOP leaves iteration `n` closed, and an owner `resume` opens `n+1` |
| Required checks missing `compat` and `control-plane` | `lanes.required` names all four CI checks; `lanes.cert_lanes` names the two host lanes a cert covers |

## 3. Verification at this head

- `python -m ruff check .` exit 0.
- `PYTHONPATH=src python -m pytest tests/unit/test_autonomy_preflight.py --no-cov` passes on
  Python 3.12 and 3.13 (counts in the WORKLOG entry for this session).
- `python autonomy/tools/preflight.py sha` equals `autonomy/loop.yaml` `policy_sha`
  `263bcae0a59fbdc031c0ce0fc81e02e8d8d5d0ecd26fa729d55da26c1dc25767`.
- `python autonomy/tools/preflight.py preflight --iteration 1` exits 1 with exactly
  `missing grant autonomy/grants/G-1.md`.
- Dry run against the reconciled gate: 15 of 15 steps as required,
  `autonomy/packets/DRYRUN-2026-09-16.md`.
- CI for this head: see `gh run list --repo WezzSide/project-atlas --branch autonomy/scaffold`,
  PR https://github.com/WezzSide/project-atlas/pull/946.

## 4. Advisory gating (not owner closure)

The supervisor subagent returned REDESIGN on the fork lineage, then ACCELERATE after its three
findings were closed; the verifier subagent returned NOT_CERTIFIED because CI had not finished
inside its budget, and found the blank-line append defect. Both ran read-only. Their findings are
recorded in `autonomy/packets/DRYRUN-2026-09-16.md`; no cert exists for any head.

## 5. Owner-gated, nothing else blocks iteration 1

Instructions and exact file contents: `autonomy/packets/OWNER-UNBLOCK-KIT-2026-09-16.md`.

1. Merge PR #946 after CI is green on the reconciled head and a verifier certifies it.
2. `git branch autonomy/staging origin/main && git push -u origin autonomy/staging`.
3. Commit `autonomy/grants/G-1.md` and `autonomy/directives/D-ATLAS-ITER-1.md` to `main`, with
   `base_sha` set to the merge commit and `policy_sha` confirmed by `preflight.py sha`.
4. Delete the stray fork `bolkdev/project-atlas-1`; rotate the PAT.
5. Decide: the two fallback-lane rules (pin the grant ref in the verifier's clone; how
   `product_perf` timing under coverage is treated), and whether
   `autonomy/instruments/skills/**` opens at level 0 or stays at level 1.

## 6. Scope note

`autonomy/audits/**` is an executor-forbidden scope (policy section 4.1), so
`preflight.py scope --role executor` flags this file, as it flagged `SHUTDOWN-2026-09-15.md`. It
exists because the owner's directive required a checkpoint. The owner should either accept the
exception or move checkpoints under a scope the executor holds. `autonomy/packets/**` is an
executor scope, so the dry-run report and the unblock kit are clean.

## 7. Resume instructions

Read `autonomy/policy.md`, then this file, then the unblock kit. Run
`python autonomy/tools/preflight.py preflight --iteration 1`: until the owner commits `G-1`, it
must fail with exactly `missing grant`. Do not start iteration work, edit `autonomy/tools/**` or
`autonomy/policy.md`, or push to `fork`.
