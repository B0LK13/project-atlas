# Conflict UX — hard invariants (PREP)

Package: **AS-2.2-CONFLICT-UX-PREP-001**  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. Cockpit ≠ auto-resolve

| Signal | Allowed | Forbidden |
|---|---|---|
| Open conflict card | Display sides + facets | Silent `state=resolved` |
| Operator action | escalate / open_evidence / request_human | `auto_resolve` / LLM winner |
| Missing disposition | show `authority_pending` / omit | Invent trust score |

Any consumer that coerces open conflict → resolved without Core promotion is
**out of contract**.

## 2. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Conflict cockpit panel | Render cards; link evidence | Write Layer B / claims |
| Disposition action | Emit escalate receipt | `_promote` / canonical write |
| Ask Atlas CONFLICTS slot | Cite projection cards | Stamp authority |

Truth boundary string (prep):  
`CONFLICT COCKPIT ≠ AUTO-RESOLVE / ≠ CANONICAL WRITE / ≠ AUTHORITY`

## 3. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority.level` on envelopes | `derived` |
| LLM-suggested winner | rejected (`llm_pick_winner`) |
| Subjective confidence / trust | **forbidden** (objective signals only) |

## 4. No runtime `conflict_projections` mutation in PREP

This PREP lane **must not** edit:

- `src/project_atlas/conflict_projections.py`
- shipped package schemas for Core conflicts
- knowledge_compiler conflict emission defaults

Consume-only references to AS-CORE2-008 helpers are documentation links, not
code ownership.

## 5. no PILOT invent / certification wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture cockpit rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock.
