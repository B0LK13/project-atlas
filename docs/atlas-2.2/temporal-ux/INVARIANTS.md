# Temporal UX — hard invariants (PREP)

Package: **AS-2.2-TEMPORAL-UX-PREP-001**  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. Cockpit ≠ silent winner

| Signal | Allowed | Forbidden |
|---|---|---|
| Overlapping covers | Display unresolved_overlap | Silent `disposition=selected` |
| Operator action | open_evidence / escalate / request_human | `silent_winner` / LLM pick |
| Missing evidence | show unresolved_incomplete | Invent current from wall-clock |

Any consumer that coerces overlap → selected without Core as-of rules is
**out of contract**.

## 2. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Temporal cockpit panel | Render cards; link evidence | Write Layer B / mutate windows |
| Temporal action | Emit escalate receipt | `_promote` / bitemporal mutation |
| Ask Atlas as-of slot | Cite lens receipts | Stamp authority |

Truth boundary string (prep):  
`TEMPORAL UX ≠ WALL-CLOCK NOW / ≠ SILENT WINNER / ≠ BITEMPORAL MUTATION / ≠ AUTHORITY`

## 3. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority.level` on envelopes | `derived` |
| LLM-suggested as-of winner | rejected (`silent_winner`) |
| Subjective confidence / trust | **forbidden** (objective signals only) |

## 4. No runtime `bitemporal` mutation in PREP

This PREP lane **must not** edit:

- `src/project_atlas/bitemporal.py`
- `src/project_atlas/temporal_evaluator.py`
- shipped package schemas for Core temporal / as-of results

Consume-only references to AS-2.0-TEMPORAL-001 helpers are documentation links,
not code ownership.

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

## Deepen PREP

See `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md` and deepen negatives under `fixtures/`.
