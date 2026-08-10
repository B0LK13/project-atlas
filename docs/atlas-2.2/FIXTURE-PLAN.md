# Atlas 2.2 — Fixture plan (Hybrid Retrieval PREP)

Status: **PREP ONLY** — sketches under `docs/atlas-2.2/fixtures/`.
Not production schemas. Not CI harness credit. Not PILOT.

## Families

| Family | Path | Purpose | Mutates vault? |
|---|---|---|---|
| hybrid-retrieval | `fixtures/hybrid-retrieval/` | Plan samples + semantic-disabled expectations | **no** |
| (reserved) semantic-index-spike | `fixtures/semantic-index-spike/` | Future isolated vector spike inputs | **no** |
| (reserved) fusion-eval | `fixtures/fusion-eval/` | Multi-slot fusion golden sketches | **no** |

## Inventory ledger

| Scenario | ID | Positive | Negative | Payloads | Runner | Gate credit |
|---|---|---|---|---|---|---|
| Exact lexical plan shape | FX-2.2-RET-001 | sketched + sample | n/a | present (docs) | absent | **NO** |
| Prefix lexical plan shape | FX-2.2-RET-002 | sketched + sample | n/a | present (docs) | absent | **NO** |
| Semantic disabled / reject | FX-2.2-RET-003 | disabled slot | enable fails closed | present (docs) | absent | **NO** |
| Fusion order sketch | FX-2.2-RET-004 | prose + JSON sketch | semantic cannot erase lexical | present (docs) | absent | **NO** |

## Creation policy

- Docs-only paths; do **not** import from `src/project_atlas/` or wire CI yet.
- Synthetic IDs and relative paths only; no host roots; no secrets.
- When post-unlock production opens, fixtures may promote to `fixtures/atlas-2.2/` with entry-gate approval.

## Cross-links

- Architecture: [HYBRID-RETRIEVAL-2.md](HYBRID-RETRIEVAL-2.md)
- Benchmarks: [benchmarks/README.md](benchmarks/README.md)
- Predecessor: [docs/AS-2.0-RET-HYBRID-001.md](../AS-2.0-RET-HYBRID-001.md)
