# A2 — Action Intent Model (schema sketch)

```text
REQUESTED != CLAIMED
PREVIEW != EXECUTION
AVAILABLE != AUTHORIZED
ATTENTION != AUTHORIZATION
STUDIO_UI != AUTHORITY
```

Studio produces **typed action intents**. An intent is a *request object*, not
a receipt of execution and not a grant of authority.

## Proposed schema const

`ATLAS_STUDIO_ACTION_INTENT_V1` — **implemented** (`schemas/atlas_studio_action_intent_v1.schema.json`).

## Fields

| Field | Type (sketch) | Meaning |
|---|---|---|
| `intent_id` | string (deterministic or UUIDv4 + material hash) | Stable id for audit / idempotency key material |
| `action_type` | enum | e.g. `OWNERSHIP_CLAIM`, later `CI_DISPATCH`, `IV_REQUEST`, `HANDOFF_GENERATE`, … |
| `actor_identity` | object | Agent id + registry status snapshot refs (presentation ≠ proof) |
| `target_refs` | list | PR / lane / residual / action_id refs from F12/F15 |
| `source_mc_fingerprint` | sha256 hex | Mission Control fingerprint that originated the candidate |
| `generated_at` | UTC timestamp | Intent creation time |
| `max_age` | seconds | Freshness bound; stale intent ⇒ REFUSE |
| `capability_claims` | list[string] | **Claims**, not grants — e.g. `["ownership_claim"]` |
| `preview_required` | bool | Must be true for first governed actions |
| `authorization_required` | bool | Must be true; Studio cannot clear this |
| `evidence_refs` | list | Links to MC/F12/F15 fingerprints, dry-run plans, prior denials |

## Honesty consts (must be true)

```text
requested_ne_claimed
preview_ne_execution
available_ne_authorized
studio_ui_ne_authority
grants_no_self_authorization
```

## Lifecycle (conceptual)

```text
CANDIDATE (from MC / F12)
  → PREVIEW (why / impact / blockers; RO)
  → INTENT_REQUESTED (Studio emits typed intent)
  → CONTROL_PLANE_EVALUATE (validity, authz, freshness, TOCTOU)
  → EXECUTED | REFUSED | EXPIRED
```

`WOULD_CLAIM` / dry-run outcomes from `atlas_dag` remain **preview evidence**,
never `CLAIMED`.

## Anti-patterns

| Anti-pattern | Correct |
|---|---|
| Intent without `source_mc_fingerprint` | Fail closed |
| Intent older than `max_age` | REFUSE `STALE_INTENT` |
| Capability listed ⇒ authorized | Capability is a claim; control plane grants |
| Attention tier 10 ⇒ auto-intent | Human/policy still required per action_type |
| Studio sets `authorization_granted=true` | Forbidden field on Studio-produced intents |
