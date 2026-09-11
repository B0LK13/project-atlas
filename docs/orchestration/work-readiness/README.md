# AS-WORK-READINESS-001 — Work readiness and handoff

**Package:** `AS-WORK-READINESS-001`  
**Directive:** `ATLAS-WORK-READINESS-AND-HANDOFF-001`  
**Module:** `project_atlas.orchestration.work_readiness`

## Purpose

Derived, explainable work-queue projection over existing backlog items, task
contracts, dependencies, ownership/claims, enrollment, and result evidence.

This package **advises** and **prepares** handoff packets. It does **not**
assign, dispatch, claim work, raise limits, or mint authorization.

## Truth boundaries

| Boundary | Meaning |
| --- | --- |
| `PROJECTION != AUTHORITY` | Queue view never grants launch/merge rights |
| `TECHNICALLY_READY != LAUNCH_AUTHORIZED` | Separate axes + buckets |
| `WORKER_EXIT_ZERO != TASK_COMPLETE` | Acceptance failure keeps lifecycle incomplete |
| `ACCEPTANCE_PASSED != INDEPENDENT_REVIEW` | Review is its own axis |
| `UNKNOWN_OWNER != AVAILABLE` | Unreadable registries never mean free capacity |
| `FIXTURE_ADAPTER != LIVE_INTEGRATION` | Fixture ports document missing PR surfaces |
| `HANDOFF_PROPOSAL != CLAIM` | `reserves_work=false`; use existing claim APIs |

## Commands

```bash
# Derived projection
atlas work-readiness project --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json --json

# Next offerable task (deterministic)
atlas work-readiness select --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json --json

# Explain one task
atlas work-readiness explain --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json --task-id WR-READY-001

# Prepare idempotent handoff (does not claim)
atlas work-readiness handoff --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json \
  --task-id WR-READY-001 --propose-for agent-codex-1 --out /tmp/wr-handoff.json

# Re-check before any real transfer
atlas work-readiness refresh --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json \
  --proposal /tmp/wr-handoff.json

# Capacity / conflict view (does not raise limits)
atlas work-readiness capacity --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json

# Read-only demo against a backlog markdown + fixtures
atlas work-readiness demo --backlog docs/backlog.md \
  --fixture tests/fixtures/work_readiness/positive_and_negative.v1.json --json
```

## Selection and exclusion rules

### Hard suitability (must all be `YES` for `OFFERABLE_TO_DISPATCHER`)

1. Content prepared (valid contract + non-empty objective)
2. Technically prepared (valid contract + mutation paths + required adapter)
3. Dependencies satisfied (no `NO` / `UNKNOWN` deps)
4. Ownership clear (no active claim on this task id)
5. Mutation conflict clear vs **active claims** (path set / prefix overlap)
6. Runtime available (`ACTIVE` enrolled agent matching adapter/capabilities)
7. Execution authorized (**verified** `authorization_ref` present — never minted here)

### Soft / separate buckets

- `CONTENT_READY_AWAITING_AUTHORIZATION` — axes 1–6 pass-ish, authorization missing
- `BLOCKED` — any hard blocker code
- `COMPLETE` — acceptance passed **and** independent review complete

### Ranking (after hard filter)

1. Higher explicit backlog `priority` first
2. Missing priority sorts **after** known priorities (not as zero)
3. Higher dependency-impact first
4. Lexicographic `task_id` tie-breaker

No model scores. No uncalibrated success predictions.

## Handoff format (`schema_version=1`)

Fields: `handoff_id`, `task_id`, `contract_id`, `contract_digest`,
`source_revisions`, `proposed_agent_or_capabilities`, `dependency_evidence`,
`ownership_evidence`, `mutation_paths`, `execution_limits`, `acceptance_refs`,
`freshness_conditions`, `observed_at`, `expired`, `expire_reason`,
`reserves_work=false`, `execution_authorized=false`, `merge_authorized=false`.

`handoff_id = wrh-` + SHA-256 prefix over `(task_id, contract_digest, source_revisions, mutation_paths)`.
Identical inputs → identical id (no duplicate tasks).

`refresh` expires a proposal when digest, revisions, mutation paths, ownership,
or bucket drift. Refresh **does not** replace the authority check before dispatch.

## Missing integrations (interface handoffs)

Documented in fixture `missing_integrations` and demo output:

1. Live `ContractPort` from `ATLAS-BACKLOG-TO-TASK-CONTRACT-001` / `AS-TASK-CONTRACT-001`
2. Live enrollment/claim ports from program supervisor (e.g. PR #797)
3. Live `ResultPort` from `ATLAS-EXECUTION-QUALITY-LOOP-001`

Until those land on the integration branch, use versioned fixtures only and do
**not** claim live integration.

## Studio handoff

No new Studio UI is required for v1. Studio owners can consume:

- `WorkQueueReport` JSON from `atlas work-readiness project --json`
- `HandoffProposal` JSON from `atlas work-readiness handoff --json`
- Selection payload from `atlas work-readiness select --json`

Suggested Studio read models: offerable / awaiting-auth / blocked lists,
shared_blockers with `dependency_impact`, deep-link via `contract_id` +
`contract_digest` + blocker `object_ref`.

## Mutation scope of this package

- `src/project_atlas/orchestration/work_readiness/`
- `src/project_atlas/cli.py` (additive register/dispatch only)
- `tests/unit/orchestration/test_work_readiness.py`
- `tests/fixtures/work_readiness/`
- `docs/orchestration/work-readiness/`
