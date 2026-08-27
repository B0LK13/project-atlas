# D-046 — F2 Frontier Falsification + Authentic Windows Certification

```text
DIRECTIVE = D-046
CASE = B_EXTERNAL_HARD_BLOCKER

INITIAL_F2_OWNER_ONLY_FRONTIER = FALSE
FINAL_OWNER_ONLY_FRONTIER = FALSE

WINDOWS_PACKET_PREPARED = YES
WINDOWS_PACKET_EXECUTED = YES
WINDOWS_HOST_AUTHENTIC = YES
WINDOWS_RESULT_CLASS = W-A
PR607_AUTHENTIC_WINDOWS_PASS = YES

PR607_EXACT_HEAD_CI = BLOCKED_EXTERNAL_RUNNER_INFRA
MERGES_PERFORMED = 0
```

## Frontier falsification

D-045 labeled F2 as owner-only while `WINDOWS_PACKET_EXECUTED = NO`.
That failed the §1 test: executable non-owner certification remained.

This host (`CYBERCOMMANDCEN`, Windows, `D:\`) is authentic and authorized.
The prepared packet was executed. F2 owner-only claim is **falsified**.

## Authentic Windows results (W-A)

| Lane | Bound object | Result |
|---|---|---|
| PR607 governance | `80dd9d01` / `0eab2f88` | PASS |
| D-045 prepared GE packet | PR608 `94786c9c` / `a26b9caa` | PASS_48 + skill.sha256 PASS |

No object mutation. No SHA transplant.

## Hosted CI (separate fact)

| Field | Value |
|---|---|
| Run | 32990010040 attempts 3+4 |
| Steps executed | 0 |
| `actions/runners` total_count | **0** |
| Classification | `BLOCKED_EXTERNAL_RUNNER_INFRA` |

Windows PASS does **not** rewrite hosted exact-head CI to PASS.

## Policy

GitHub main branch protection: required status checks **not enabled** (404).
Atlas governance/SDK still treats exact-head CI job matrix as a soft gate.
No written policy authorizes Windows PASS to substitute for hosted CI PASS.

Therefore:

```text
PR607_OWNER_READY = YES
PR607_MERGE_ELIGIBLE_UNDER_REPOSITORY_POLICY = NO
```

## Terminal condition

```text
CASE = B EXTERNAL_HARD_BLOCKER
ACTIVE_BLOCKER = GITHUB_ACTIONS_RUNNER_INFRA
UNBLOCK = restore Actions runners/billing, then rerun exact-head CI on 80dd9d01
READY_NON_OWNER_NODES_REMAINING = 0
```

Not labeled OWNER_ONLY per D-046 §8.

Machine: `D-AUG27-F2-FALSIFICATION-WINDOWS-CERT-046.json`
