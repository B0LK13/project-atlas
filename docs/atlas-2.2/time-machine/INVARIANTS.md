# Knowledge Time Machine — hard invariants (PREP deepen)

Package: **AS-2.2-TIME-MACHINE-DEEPEN-PREP-001**  
Status: **normative for this deepen tree**; runtime enforcement deferred until unlock.

## 1. As-of ≠ Layer B authority

| Signal | Allowed | Forbidden |
|---|---|---|
| As-of snapshot | `authority.level=derived`, read-only consume | Promote to claims / concepts |
| Selected claim row | Cite claim_id + disposition at *T* | `_promote` / canonical write |
| Fixture rehearsal | Assert derived snapshot shape | Stamp Layer B / project authority |

Truth boundary:  
`TIME MACHINE AS-OF ≠ LAYER B AUTHORITY / ≠ ESTATE FACTS / ≠ PILOT PASS`

## 2. Diff ≠ mutation

| Signal | Allowed | Forbidden |
|---|---|---|
| Knowledge diff | Derived delta blocks (claim/graph/decision) | Apply diff as Layer B mutation |
| Diff units | added · removed · changed · unresolved_delta | Fabricated ids / silent approval |
| Decision diff | Disposition transition sketch | Human approval by diff alone |

Truth boundary:  
`TIME MACHINE DIFF ≠ LAYER B MUTATION / ≠ HUMAN APPROVAL`

## 3. No silent overlap winner

| Signal | Allowed | Forbidden |
|---|---|---|
| Overlapping validity covers | `unresolved_overlap` in snapshot/diff | Pick lexicographic / recency winner |
| As-of selection | Single cover → selected | Tie-break without explicit rule |
| Diff on overlap delta | `unresolved_delta` units | Collapse to changed without citation |

Reuses AS-2.0-TEMPORAL-001 fail-closed semantics; Time Machine must not weaken them.

## 4. Wall-clock ≠ valid-time input

| Signal | Allowed | Forbidden |
|---|---|---|
| `as_of_valid_time` | Declared ISO-like *T* (evidence-backed) | `now`, `today`, process clock |
| Knowledge boundary | Optional `knowledge_compilation_id` | Wall-clock as knowledge-time proxy |
| Malformed input | `rejected_malformed` | Silent normalization to current |

## 5. Graph ≠ authority

| Signal | Allowed | Forbidden |
|---|---|---|
| Graph diff block | `authority.level=derived` on entities/edges | Elevate graph slot to Layer B |
| Centrality / ranking | Display ordering only | Winner selection from graph metrics |
| Graph-as-truth | Derived projection at *T* | Replace claim authority |

Truth boundary:  
`GRAPH DIFF ≠ AUTHORITY`

## 6. TEMPORAL-001 ≠ dual own

This PREP lane **must not** edit or dual-own:

- AS-2.0-TEMPORAL-001 single subject/field window + as-of
- `src/project_atlas/bitemporal.py` runtime defaults / package_id
- `docs/atlas-2.2/temporal-ux/` UX PREP (peer)

Time Machine multi-claim snapshot + T1–T2 diffs are a **distinct read lens** with
pattern alignment only.

## 7. LLM ≠ authority / no trust scores

| Field | Const / rule |
|---|---|
| `llm_authority` | **forbidden** |
| LLM similarity as diff winner | **forbidden** |
| Subjective confidence / trust | **forbidden** |

## 8. Release / unlock wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| Snapshot / diff stamps | Never WEB ACCEPTED / RELEASE / 2.1 cert |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture Time Machine rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock. **DEMO VERIFIED ≠ release certification.**
