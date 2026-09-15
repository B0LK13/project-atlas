# ADR-025 — Research workspace + Ask Atlas 2 prep (SAFE pre-v2.1.0)

## Status

Accepted for **PREP artifacts only**. Runtime implementation **deferred** until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.

## Context

Atlas 2.1 tip (`f45134f`, prior harden drain `a1e0972`) has Track B harden
lanes drained. North-star gap analysis
identifies Research Workspaces, Evidence Packs, and a deepened Ask Atlas answer
surface as 2.2 intelligence themes. Pre-unlock policy allows additive docs /
contracts / fixtures under `docs/atlas-2.2/` without dependency-bearing Core
mutation.

## Decision

1. Seed package **AS-2.2-RESEARCH-001** with the pipeline
   `question → hypotheses → evidence → conflicts → synthesis → packs`.
2. Keep JSON Schema stubs under `docs/atlas-2.2/contracts/research/` (not
   package data).
3. Keep fixture sketches under `docs/atlas-2.2/fixtures/research/` with
   `evidence_class=fixture-only` and zero pilot roots.
4. Define Ask Atlas 2 answer fields without mutating the 2.1 live Ask path.
5. Forbid production imports / CI gate promotion until unlock + contract freeze.

## Consequences

- Parallel-safe with other 2.2 prep PRs (own directory subtree).
- No change to `src/project_atlas/` behavior or defaults.
- Future implementation must pin `v2.1.0` compat and preserve
  LLM≠authority / UI≠canonical / Graph≠authority.

## Non-claims

- Not `ATLAS_2_1_RELEASE_CERTIFIED`
- Not authentic estate PILOT PASS
- Not embeddings / vector product delivery
