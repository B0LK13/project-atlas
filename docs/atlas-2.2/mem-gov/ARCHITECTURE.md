# Governed agent memory — architecture (PREP)

Package: **AS-2.2-MEM-GOV-001**  
Status: **PREP ONLY** — non-normative until 2.2 unlock + contract freeze.

## Problem

Agents accumulate session notes, preferences, and derived reminders. Without
governance those artifacts:

- lose provenance (“who said this, from which receipt?”)
- stay retrievable after operator withdrawal or skill-policy rotation
- never expire, presenting stale context as current
- fork silently when two writes share a logical key

Atlas already has **receipt revocation** (AS-INT-011) and **tombstones**
(AS-INT-010) for agent-event packages. Governed **memory** is a distinct
operational plane: durable, consume-only units agents may re-read, still never
Layer B authority.

## Design sketch

```text
  session / event / receipt
            │
            v
   ┌────────────────────┐
   │ memory write       │  provenance REQUIRED
   └─────────┬──────────┘
             v
   ┌────────────────────┐
   │ agent-memory-record│  status=active
   └─────────┬──────────┘
      ┌──────┼──────────────┐
      v      v              v
  revoke   expire      supersede
      │      │              │
      v      v              v
  revoked  expired     superseded ──▶ newer memory_id
```

## Planes

| Plane | Role |
|---|---|
| Truth | `operational` only |
| Authority | `none` — memory never writes claims / concepts / winners |
| Consume | Context compiler / Agent OS / Ask surfaces may read **active** units |

## Four governance axes

### 1. Provenance (mandatory)

Every record must carry:

| Field | Meaning |
|---|---|
| `content_sha256` | SHA-256 of canonical memory body bytes |
| `source_receipt_id` | Binding receipt / package id (min length 1) |
| `session_id` | Agent OS / control-plane session id |
| `event_id` (optional) | Agent-event id when memory derives from an event |
| `vault_identity` (optional) | Vault binding when present; fail-closed on mismatch post-unlock |

No provenance ⇒ reject write (future impl). Fixtures without provenance are
invalid by schema.

### 2. Revocation

Mirrors receipt-revocation **reasons**, scoped to memory units:

| Reason | Default status | Meaning |
|---|---|---|
| `operator` | `revoked` | Explicit operator withdrawal |
| `skill_policy` | `revoked` | Skill / readiness rotation withdrew trust |
| `integrity` | `revoked` | Hash / binding integrity failure |

Revocation does **not** delete files. Retrieval must treat revoked as absent.
Distinct from AS-INT-011 indexes (those cover event receipts).

### 3. Expiry

| Field | Rule |
|---|---|
| `expires_at` | Optional ISO-8601 / deterministic timestamp string on the record |
| `as_of` | Injected evaluation input only — never wall-clock `now` inside writers |
| Past expiry | Effective status `expired` for retrieval; stored status may remain `active` until compaction |

Inverted windows (`expires_at` < `written_at` when both present) reject.
Missing `as_of` on expiry-sensitive APIs fail closed (future impl).

### 4. Supersession

| Field | Rule |
|---|---|
| `memory_key` | Logical identity; at most one **active** record per key per project scope |
| `supersedes` | Prior `memory_id` this write replaces |
| `superseded_by` | Filled on the prior record when replacement commits |
| Conflict | Two actives for same key without supersession edge ⇒ fail closed / quarantine |

Supersession is reciprocal when both records exist. Orphan `supersedes`
pointers ⇒ INCOMPLETE / reject (no silent invent).

## Retrieval rules (fail-closed)

1. `status ∈ {revoked, expired, superseded}` ⇒ not returned as active.
2. `status=active` but `as_of` ≥ `expires_at` ⇒ treat as expired.
3. Every returned unit still carries provenance pointers.
4. Secrets findings are metadata-only; never embed matched secret content.
5. Deterministic ordering: `memory_key`, then `memory_id` (`sort_keys` JSON).

## Relationship to existing substrate

| Substrate | Relationship |
|---|---|
| AS-INT-011 receipt revocation | Pattern cousin; **do not dual-own** receipt indexes |
| AS-INT-010 tombstones | Deletion state for packages; memory may reference but not rewrite |
| AS-2.0-AGENTOS-001 | Session envelope supplies `session_id` / skill binding |
| AS-2.0-CTX-001 / CTX compiler | Consumers of active memory pointers (derived packages) |
| Core authority / claims | **Out of plane** — memory never promotes |

## Out of scope (this prep)

- Python module under `src/project_atlas/`
- CLI `atlas memory …`
- Shipping JSON Schema as package data
- Mutating 2.1 live API / MCP / web / authz / L3
- Vector / embedding memory stores as authority

## Promotion gate (future)

Implementation opens only after:

1. `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
2. Charter + compat pin packages
3. Contract freeze checklist for `atlas.2.2.agent_memory.*`
4. Explicit sole-writer ownership vs INT-011 / CTX surfaces
