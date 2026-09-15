# Ask Atlas 2 — answer surface (PREP)

Package: **AS-2.2-RESEARCH-001** (Ask Atlas 2 facet)  
Status: **PREP ONLY**

## Relationship to Ask Atlas 1.x / 2.1

| Generation | Package | Maturity |
|---|---|---|
| Ask Atlas contract | AS-2.0-WEB-ASK-001 | Thin read-only contract |
| Ask Atlas live | AS-2.1 ask path | LIVE_READ_ONLY match lens |
| **Ask Atlas 2** | **AS-2.2-RESEARCH-001** | Research-backed answer shape (prep) |

Ask Atlas 2 does **not** reopen or replace the 2.1 live match path. It deepens
the **answer envelope** once Research Workspaces exist.

## Required answer fields

| Field | Meaning |
|---|---|
| `ANSWER` | Bounded statement or explicit inability |
| `WHY` | Supporting evidence / hypothesis links |
| `WHY_NOT` | Rejected alternatives / missing support |
| `EVIDENCE` | Provenance pointers (minItems ≥ 0; empty ⇒ UNKNOWN) |
| `AUTHORITY` | Objective authority signals only (no trust scores) |
| `TEMPORAL_VALIDITY` | Valid/transaction windows when known |
| `CONFLICTS` | Retained incompatibilities |
| `UNKNOWN` | Explicit unanswered facets |

## Truth boundary

```text
ASK ATLAS 2 ≠ CANONICAL WRITE / ≠ AUTHORITY / UI ≠ TRUTH
```

- `canonical_write` always `false`
- `ui_truth` always `false`
- `graph_authority` always `false`
- `llm_authority` always `false`

## Consume path (future)

1. Research workspace emits `research-evidence-pack`
2. Ask Atlas 2 projects pack → `ask-atlas-2-answer`
3. Web / MCP / CLI read lenses render answer fields
4. No Layer B mutation on any path
