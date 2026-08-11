# REMEDI — CLAUDE-ADV005-009 / CLAUDE-ADV005-013 / CLAUDE-ADV005-019

| Field | Value |
|---|---|
| Tip base | `b0d4413cc5591a9cc789101db95b3f2cd3621afe` |
| Branch | `hotfix/adv005-claude-009-isolation` |
| WT | `D:\atlas-worktrees\remedi-claude-009` |
| Role | Group C remediator (≠ validators) |
| #291 | **UNTOUCHED** |
| OPT | **NO** |
| MERGE | **NO** until dual IV |

## Repro inputs (accepted)

| ID | Sev | Disposition | Evidence |
|---|---|---|---|
| CLAUDE-ADV005-009 | HIGH | REPRODUCED | `CLAUDE-REPRO-292/REPRO.md` |
| CLAUDE-ADV005-013 | MED | REPRODUCED | `CLAUDE-REPRO-292/REPRO.md` |
| CLAUDE-ADV005-019 | MED | REPRODUCED | `CLAUDE-REPRO-292/REPRO.md` |

## Fix (minimal tip hotfix)

| File | Change |
|---|---|
| `src/project_atlas/hybrid_retrieval.py` | Required `project_id` (fail-closed); query byte/term bounds; wrap substrate `ValueError` as `HybridRetrievalError` |
| `src/project_atlas/retrieval.py` | Optional `project_id` filter on `lookup` / `bm25_corpus` |
| `src/project_atlas/schemas/hybrid-retrieval-*.schema.json` | `project_id` in query contract |
| `tests/unit/test_as_ret_hybrid_p2_rrf.py` | Isolation + bounds + error-contract regression |

## Local probes

| Probe | Result |
|---|---|
| `probe-run.txt` / `probe-results.json` | `PROJECT_ISOLATION = PASS` |
| 009 shared-token | `b-auth-gate` absent under `PROJECT_A` scope |
| 009 keyed | only `a-*` ids |
| 013 repeat_50k / distinct_20k | rejected (`query-too-long` / `query-too-many-terms`) |
| 019 missing indexes | `HybridRetrievalError` (not bare `ValueError`) |

## Gate flags

```text
CLAUDE-ADV005-009 = REMEDIATED
CLAUDE-ADV005-013 = REMEDIATED
CLAUDE-ADV005-019 = REMEDIATED
PROJECT_ISOLATION = PASS
QUERY_BOUNDS = PASS
ERROR_CONTRACT_UNIFIED = PASS (hybrid surface)
```

## One-line summary

Hybrid RRF/plan require `project_id`, scope BM25+lexical to that project, bound query size, and normalize missing-index failures to `HybridRetrievalError`.
