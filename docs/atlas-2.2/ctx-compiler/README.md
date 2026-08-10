# AS-2.2-CTX-COMPILER-001 — Task-specific Context Compiler (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-CTX-COMPILER-001** |
| Class | **PREP** (SAFE pre-`v2.1.0`) |
| Maturity target (post-unlock) | LIVE production path for task→package compilation |
| Current maturity | CONTRACT / FIXTURE sketches only |
| Depends (post-unlock) | `AS-2.2-COMPAT-PIN-001`, hybrid retrieval deepen, Core authority/freshness/conflict substrate |
| Soft depends | `AS-2.0-CTX-001` / `AS-2.0-CTX-002` (consume, do not redefine) |
| Owned surface (prep) | `docs/atlas-2.2/ctx-compiler/**`, `docs/atlas-2.2/contracts/ctx-compiler/**`, `docs/atlas-2.2/fixtures/ctx-compiler/**`, `docs/atlas-2.2/adr/ADR-2.2-001-*` |
| Excluded surface | `src/project_atlas/**`, `src/atlas_contracts/**`, production schemas, CLI wiring |
| Directive | `D-PROJECT-ATLAS-FORCED-MULTIAGENT-ORCHESTRATION-001` · gap `GAP-NS-002` deepen |
| Evidence | `atlas-2.1-productionization-001` |

## Objective

Design a **task-specific Context Compiler** that selects evidence-backed
context for agents and UX without inventing estate facts or promoting LLM
output to authority.

## Pipeline (normative for future impl)

```text
task
  → candidates
  → authority
  → freshness
  → conflicts
  → budget
  → package
```

Extended review stages (still derived, still non-authority):

- **relevance** — profile/task fit after conflict filtering
- **privacy** — secrets / sensitive-path exclusion before budget packing

## Truth boundary

`CONTEXT COMPILER ≠ ESTATE FACTS / ≠ AUTHORITY / ≠ PILOT`

- Output packages remain **derived**
- Every item carries provenance + inclusion reason
- Absent evidence stays absent (`unknown ≠ healthy`)
- Conflicts never auto-resolve to a silent winner
- Budget truncation is explicit and reconstructable

## Non-claims (this PREP)

- Not production CLI / module under `src/`
- Not a replacement for `AS-2.0-CTX-001` fixture packs
- Not embeddings / vector authority
- Not authentic estate PILOT evidence
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`

## Deliverables in this PREP

| Artifact | Path |
|---|---|
| Architecture | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Profiles | [`PROFILES.md`](./PROFILES.md) |
| Package contract | this file |
| ADR | [`../adr/ADR-2.2-001-context-compiler-pipeline.md`](../adr/ADR-2.2-001-context-compiler-pipeline.md) |
| Schema drafts | [`../contracts/ctx-compiler/`](../contracts/ctx-compiler/) |
| Fixtures | [`../fixtures/ctx-compiler/`](../fixtures/ctx-compiler/) |

## Entry gate (future production package)

1. `v2.1.0` certified → unlock event fired
2. Compat pin to 2.1 anchor
3. Schema freeze review for `atlas.2.2.context-compiler.*`
4. Sole-writer ownership of future `project_atlas.context_compiler` (name TBD)
5. ADV + IV lanes scheduled; implementer cannot self-certify
