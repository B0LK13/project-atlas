# Atlas 3 — Cross-LLM reconciliation

AT3-041 / AT3-042 / AT3-044 / AT3-049.

## Deduplication

Multiple conversations often repeat the same knowledge.

Detect:

- exact content-hash duplicates
- normalized-text near-duplicates (deterministic token overlap)
- semantic duplicates (future; not required to invent embeddings here)

Never erase original source provenance.
One reconciled object may cite many evidence sources.

## Conflicts

Do not collapse **current state**, **intent**, and **historical state**
into one scalar fact.

Example (acceptance fixture):

| Source | Statement |
|---|---|
| ChatGPT | Project uses PostgreSQL 16 |
| Claude | Owner decided to rollback to PostgreSQL 15 |
| Gemini | Migration to PostgreSQL 16 remains planned |
| Repo + deploy | PostgreSQL 15 |
| Owner statement | Keep production on 15; migrate after extension replacement |

Expected:

```text
CURRENT OBSERVED STATE = PostgreSQL 15
INTENT = PostgreSQL 16 later
CONFLICTED_HISTORY = YES
STALE_CHATGPT_MEMORY = YES
OWNER_DECISION = only if explicit owner evidence exists
NEXT AGENT CONTEXT must not say current production is PostgreSQL 16
PROMOTED_TO_TRUTH_CORE = 0 unless separately governed
```

Claude saying “owner decided” **without** `owner_origin` is
`proposed_decision`, not a confirmed owner decision.

## Freshness

Every extracted memory supports, where justified:

`CURRENT` · `STALE` · `SUPERSEDED` · `CONTESTED` · `UNKNOWN`

A conversation item becomes stale when stronger later evidence invalidates
its assumptions (code, config, deployment, explicit owner statement).

Context Compiler must not present stale memory as current truth.

## Promotion

```text
CAPTURE != CANONICAL FACT
REVIEWED != AUTOMATICALLY TRUE
PROVIDER MEMORY != PROJECT REALITY
```
