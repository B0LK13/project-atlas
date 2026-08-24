# D-149R5 — Independent-IV residuals

**Package:** `AS-D149R5-IV-RESIDUALS-001`  
**Base main:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Base tree:** `e9919f5d04bd1613df7254e3281badcdd7832b86`  
**Predecessor:** draft `#449` (`1c558b1ae94f201e809fed84527f2dfdbe4ec2f0`)  
**Branch:** `cursor/atlas-autonomous-night-cycle-d7ae`  
**Merge authorization:** `NOT_GRANTED`

## Independent review of `#449`

An independent explore-lane review of `#449` classified F-001 through F-010
(P0/P1 owner-gate escalation, capability grant, mutation order, complete-after-O2,
SUPERSEDED MERGE→CREDENTIAL, stale evidence) as **FIXED** on that branch.

Three VALID residuals remained:

| ID | Severity | Residual |
|---|---|---|
| F-011 | P2 | 5000-file content-hash cap hid overflow corpus drift |
| F-012 | P2 | Runner left credential/DAG mutated if O2 failed after apply |
| F-013 | P2 | Missing git HEAD skipped the live-main pin check |

## Fixes

- `estate_fingerprint()` binds full path+size inventory and streamed
  content hashes for every collected file, including overflow files.
- `estate_credential_binding_current()` fail-closes when live HEAD cannot be
  resolved.
- `run_authentic_o2()` snapshots orchestration state before mutation and
  restores nodes/credential/objectives/cert/checkpoint/mission-state if the
  post-mutation pipeline raises.

## Tests

- `test_fingerprint_overflow_inventory_invalidates_unhashed_file`
- `test_fingerprint_overflow_new_file_invalidates_credential`
- `test_nongit_repo_cannot_bind_present_credential`
- `test_runner_exception_after_mutation_restores_state`

## Not claimed

- `AUTHENTIC_PILOT=YES`
- Owner merge authorization
