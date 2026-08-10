# Ask Atlas 2 deepen — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Deepen the Ask Atlas 2 answer surface beyond the research-ask2 flat envelope
into **citation-backed, multi-lens consume projections** — without mutating
`ask_atlas_live.py`, without dual-owning research stubs, and without claiming
2.1 release credit.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Web / MCP / CLI lenses — consume-only                      │
│  UI ≠ canonical · LLM ≠ authority · Ask2 ≠ live mutate      │
├─────────────────────────────────────────────────────────────┤
│  2.2 Ask Atlas 2 deepen (future AS-2.2-ASK2-001)            │
│    project(pack) → Ask2DeepenAnswerView                     │
│    chain(answer_id) → Ask2CitationChain                     │
│    lens(surface) → Ask2LensProjection                       │
│    propose(action) → Ask2ForbiddenAction (fail-closed)      │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on tip — consume only / conceptual)     │
│    AS-2.2-RESEARCH-001 answer envelope (8 fields)           │
│    research-evidence-pack → ask-atlas-2-answer projection   │
│    AS-2.0-WEB-ASK-001 thin contract ancestor                │
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own / do not mutate)                 │
│    ask_atlas_live.py — 2.1 LIVE_READ_ONLY match lens        │
│    AS-2.2-CONFLICT-UX-PREP-001 — CONFLICTS card peer        │
│    contracts/research/ask-atlas-2-answer.schema.json        │
└─────────────────────────────────────────────────────────────┘
```

## Substrate mapping

| Bucket | Source package | Emit path (conceptual) | Prep rule |
|---|---|---|---|
| Flat answer envelope | AS-2.2-RESEARCH-001 | research answer stub | Peer; do not relocate |
| Evidence packs | AS-2.2-RESEARCH-001 | research-evidence-pack | Consume; deepen cites pack_id |
| Live match lens | AS-2.1 ask path | `ask_atlas_live.py` | **Do not mutate** |
| Conflict presence | AS-2.2-CONFLICT-UX-PREP-001 | cockpit cards | Soft peer for CONFLICTS |
| Deepen answer view | this PREP | docs stubs only | Unique path under ask-atlas-2/ |

## Deepen answer view (conceptual)

A deepen result is a **derived, deterministic** envelope:

- `question_id` / `answer_id` / `pack_id` — stable fixture IDs
- required research fields: `ANSWER`, `WHY`, `WHY_NOT`, `EVIDENCE`,
  `AUTHORITY`, `TEMPORAL_VALIDITY`, `CONFLICTS`, `UNKNOWN`
- `citation_chain` — ordered evidence→hypothesis→pack nodes
- `lenses[]` — web / mcp / cli projections with field presence
- `authority.level = derived`
- `canonical_write = false`
- `ui_truth = false`
- `graph_authority = false`
- `llm_authority = false`
- `live_path_owned = false`
- `atlas_2_1_release_certified = false` on all prep fixtures

## Non-goals

- Mutating `project_atlas.ask_atlas_live` or replacing LIVE_READ_ONLY
- Relocating / rewriting research-ask2 stubs under `contracts/research/`
- Subjective trust / confidence scores
- Authentic estate PILOT evidence from fixtures
- Claiming RELEASE CERTIFIED from deepen rehearsal

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: deepen prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped
