# AS-STUDIO-A2-001 — evidence (Governed OWNERSHIP_CLAIM + substrate)

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
AS_STUDIO_A2_GOVERNANCE_SUBSTRATE = IMPLEMENTED_IN_LANE
FIRST_GOVERNED_ACTION = OWNERSHIP_CLAIM
PREVIEW != EXECUTION = ENFORCED
EXECUTION_TIME_REVALIDATION = FAIL_CLOSED
STUDIO_SELF_AUTHORIZATION = IMPOSSIBLE_WITHIN_PROVEN_SCOPE
DISPATCH = NOT_STARTED
STEAL_AUTO_EXECUTION = NOT_STARTED
MERGE_AUTHORIZATION = NOT_GRANTED
CI_PASS != FORMAL_IV
IMPLEMENTED != MERGED
```

## Exact objects

| Field | Value |
|---|---|
| Package | `AS-STUDIO-A2-001` |
| Branch | `feat/as-studio-a2-001` |
| Base | A1 tip / PR #770 |
| HEAD | `3e0fc72339bbef502013587e2fde677352981769` |
| Local tests | 68 passed (A0+A1+A2+substrate); ruff PASS; doctor PASS |
| Exact-head CI | PASS — run `34358065961` on tip `3e0fc723` (substrate `64fe1afa`) |
| Modules | `scripts/atlas_studio/governance.py`, `action_intent.py` |
| Schemas | `atlas_studio_action_{intent,preview,decision}_v1.schema.json` |
| CLI | `claim-candidates`, `claim-preview`, `claim-intent`, `claim-evaluate`, `claim-execute` |
| Tests | `test_atlas_studio_a2_governed_claim.py`, `test_atlas_studio_a2_governance_substrate.py`, `test_atlas_studio_a2_review_closure.py` |
| Docs | `A2-GOVERNANCE-SUBSTRATE.md` |
| ADR | ADR-035 |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a{0,1,2}*.py \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py -q --tb=short --no-cov
.venv/bin/python -m ruff check scripts/atlas_studio \
  tests/unit/test_atlas_studio_a2_governed_claim.py \
  tests/unit/test_atlas_studio_a2_governance_substrate.py
.venv/bin/python scripts/atlas-studio.py doctor --json
```

## Flow enforced

```text
MC truth → candidate (F12 OWNERSHIP_CLAIM) → preview → intent
→ governance.evaluate_governed_intent → execute|refuse via emitter OWNER_CLAIMED
→ decision evidence
```

Claim is registered as the first `ActionHandler` instance; futures
(`CI_DISPATCH`, `IV_REQUEST`, `HANDOFF_DELIVER`, `STEAL_EXECUTE`, `MERGE`,
`WORKTREE_OPEN`) are declared `NOT_STARTED` and refuse closed.

## Refusal codes

`EXECUTE_ALLOWED` (evaluate verdict; also the dry-run label with `dry_run=true`),
`EXECUTED` (wet, confirmed, `mutated=true` only), `REFUSED_STALE`,
`REFUSED_ALREADY_OWNED`, `REFUSED_NOT_RUNNABLE`, `REFUSED_AGENT_INVALID`,
`REFUSED_CAPABILITY`, `REFUSED_POLICY`, `REFUSED_TARGET_MISMATCH`,
`REFUSED_IDEMPOTENT_ALREADY_CLAIMED`, `REFUSED_SCHEMA`,
`REFUSED_UNSUPPORTED_ACTION`, `EXECUTION_FAILED` (executor raised / invalid
return; `evidence.mutation_state=UNKNOWN`)

## Review-closure hardening (PR #776 findings)

| Finding | Source | Fix | Test |
|---|---|---|---|
| `claim-execute` without `--repo` skipped repo pinning (`expected_repo=None`) | Copilot review, cli.py | `_emit_ownership_claim` refuses `EXPECTED_REPO_REQUIRED_AT_EXECUTE`; CLI `--repo` required | `test_wet_execute_without_expected_repo_refuses_before_resolve`, `test_wet_execute_with_wrong_expected_repo_refuses`, `test_cli_claim_execute_requires_repo` |
| No-op `[c for c in candidates if True]` | Copilot review, action_intent.py | Removed; agent bind stays in `build_frontier_matrix` + `AGENT_MATRIX_MISMATCH` | `test_list_claim_candidates_refuses_foreign_agent_matrix` |
| `register_action` silently overwrote an IMPLEMENTED handler | freeze handoff §3.9 | `DUPLICATE_REGISTRATION` refusal; `replace=True` explicit; same-object idempotent | `test_duplicate_registration_refused`, `test_ownership_claim_handler_cannot_be_silently_taken_over`, `test_explicit_replace_is_allowed`, `test_not_started_attach_point_can_be_promoted` |
| Executor exception escaped the substrate without evidence | freeze handoff §3.6 | `EXECUTION_FAILED` decision, `mutation_state=UNKNOWN`; invalid return also `EXECUTION_FAILED` | `test_executor_exception_becomes_execution_failed`, `test_executor_invalid_return_becomes_execution_failed`, `test_executor_failure_never_raises_from_claim_wet_path` |
| Dry-run labelled `EXECUTED` | freeze handoff §3.4 | Dry-run returns `EXECUTE_ALLOWED` + `dry_run=true` (DRY_RUN != EXECUTED); CLI exit 0 only on that pair or on `EXECUTED`+`mutated` | `test_dry_run_label_is_execute_allowed_not_executed`, `test_cli_claim_execute_dry_run_exit_code_and_label` |

Semantic change disclosed for owner veto: the dry-run label moved from
`EXECUTED` to `EXECUTE_ALLOWED`; `EXECUTION_FAILED` was added to the decision
schema enum; `claim-execute --repo` became mandatory.

## Non-claims

No dispatch, steal auto-execution, merge, IV, handoff delivery, worktree, PTY.
A1 Mission Control remains usable without A2 mutation context.
Interface is not the source of authority.
