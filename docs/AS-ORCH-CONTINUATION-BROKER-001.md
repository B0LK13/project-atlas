# AS-ORCH-CONTINUATION-BROKER-001

```
PACKAGE = AS-ORCH-CONTINUATION-BROKER-001
DIRECTIVE = D-AUTONOMOUS-CURSOR-SDK-DURABLE-AGENT-RUNTIME-082
PRIMARY_CONTINUATION_BACKEND = CURSOR_SDK_DURABLE_AGENT_RUNTIME
STOP_HOOK_BACKEND = CURSOR_STOP_HOOK_FOLLOWUP (FALLBACK)
REUSES = AS-ORCH-001D + AS-ORCH-001E
SECOND_GOVERNOR = FORBIDDEN
SECOND_DISPATCHER = FORBIDDEN
PR400_CONSUMED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

Lifecycle continuation for the primary governor. Cursor agents are workers.
`RUN_TERMINAL != DAG_END`. Not task-decision authority. Not merge authority.

## Primary backend

Official `cursor-sdk` (>=1.0.25) via `atlas orchestrator governor-service-run`.

The durable supervisor:

1. Recovers agent/run registries on startup (`Agent.resume`)
2. Ingests terminal runs
3. Recomputes the primary governor DAG
4. Creates or follows up SDK runs with idempotency keys
5. Never asks a human to continue

Cloud agents (`bc-…`) execute governed implementation / IV / ADV.
Local agents (`agent-…`) cover authentic Windows / Obsidian / filesystem work.

## Fallback backend

The Cursor stop-hook `followup_message` path remains for:

- safety assertions
- legacy UI agent compatibility
- owner-prompt suppression
- optional failsafe continuation

It is **not** the primary autonomous scheduler.

`governor-loop-tick` (001E) remains the in-process tick. Resource
exhaustion enqueues `RESOURCE_YIELD` instead of `OWNER_REQUIRED`.

## Invariants

- One primary governor
- At most one unconsumed successor per pin (stop-hook fallback)
- Idempotent SDK runs (`repo + dag_generation + node_id + role + attempt`)
- Independent roles never share implementer lineage
- Stale main/tree checkpoints fail closed
- Foreign `repository_identity` fail closed
- Worker/session/run terminal ≠ DAG terminal
- Owner-gate fingerprint emits at most one prompt
- Result / followup / SDK output cannot grant merge, execution, or authority
- `AgentBusyError` reconciles to the active run (no duplicate worker)
- Stream loss is not worker failure
- Cost metrics are not authority

## Certification (D-082)

Requires official SDK smoke + caller-disconnect resume + multi-agent
orchestration + owner-prompt dedupe + focused tests / ruff / mypy /
exact-head CI / independent IV / ADV with NEW_P0=0 and NEW_P1=0.
Certification does not grant merge.
