# Governed agent memory — hard invariants (PREP deepen)

Package: **AS-2.2-MEM-GOV-DEEPEN-PREP-001**  
Status: **normative for this deepen tree**; runtime enforcement deferred until unlock.

## 1. Memory ≠ Layer B authority

| Signal | Allowed | Forbidden |
|---|---|---|
| Memory record | `authority_plane=none`, `consume_only=true` | Promote to claims / concepts |
| Retrieval consumer | Read active units as derived context | `_promote` / canonical write |
| Fixture rehearsal | Assert non-authority plane | Stamp Layer B / project authority |

Truth boundary:  
`AGENT MEMORY ≠ LAYER B AUTHORITY / ≠ ESTATE FACTS / ≠ PILOT`

## 2. Provenance required

| Field | Rule |
|---|---|
| `content_sha256` | Required on every record |
| `source_receipt_id` | Required binding |
| `session_id` | Required binding |
| Missing provenance | reject write (future impl); invalid fixture |

No provenance ⇒ **out of contract** for governed memory.

## 3. No dual-active fork

| Signal | Allowed | Forbidden |
|---|---|---|
| Same `memory_key` | One `status=active` with supersession edge | Two actives without supersession |
| Supersession | Reciprocal `supersedes` / `superseded_by` | Silent fork / orphan pointer |
| Retrieval | Return newest active only | Merge conflicting actives |

## 4. Revoked / expired / superseded ≠ active retrieval

| Status | Retrieval |
|---|---|
| `revoked` | Absent (terminal) |
| `expired` (effective) | Absent at injected `as_of` |
| `superseded` | Absent; successor may be active |
| `active` + past `expires_at` | Treat as expired |

## 5. INT-011 ≠ dual own

This PREP lane **must not** edit or dual-own:

- AS-INT-011 receipt revocation indexes
- `src/project_atlas/knowledge_compiler.py` authority emit
- Core claims / conflict / review queue roots

Memory revocation is a **distinct operational axis** with pattern alignment only.

## 6. LLM ≠ authority / no trust scores

| Field | Const / rule |
|---|---|
| `authority_plane` | `none` |
| LLM prose as memory body | Allowed with provenance | Must not stamp authority |
| Subjective confidence / trust | **forbidden** |

## 7. Certification / unlock wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture memory rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock.
