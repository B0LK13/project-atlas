# AS-2.0-API-001 matrices

## API_ENDPOINT_MATRIX

| Method | Path | Scope | Writes | Auth delta | Notes |
|---|---|---|---|---|---|
| GET | `/v1/intelligence/evidence` | project | NO | none (`api.read`) | assessments + provenance |
| GET | `/v1/intelligence/conflicts` | project | NO | none | candidates; does not replace `/v1/conflicts` |
| GET | `/v1/intelligence/explain` | project | NO | none | explain-why trace |
| GET | `/v1/intelligence/query` | project | NO | none | certified kinds only |
| GET | `/v1/project-state` | project | NO | none | derived state |
| GET | `/v1/project-attention` | project | NO | none | risk ≠ fact |
| GET | `/v1/portfolio-state` | portfolio | NO | none | explicit cross-project |

POST intelligence = `405 writes-forbidden`.

## API_TRUTH_MATRIX

| Signal | Value |
|---|---|
| DERIVED_INTELLIGENCE_IS_AUTHORITY | NO |
| API_RESULT_IS_AUTHORITY | NO |
| CONTRADICTION_IS_PROVEN_FALSEHOOD | NO |
| RISK_IS_FACT | NO |
| ATTENTION_RANK_IS_SCORE | NO |
| GAP_PRIORITY_IS_FACT | NO |
| DEPENDENCY_IS_INFERRED | NO |
| DECISION_ENGINE_IS_AUTHORITY | NO |
| DECISION_CANDIDATE_IS_COMMAND | NO |
| UNKNOWN_IS_VALID | YES |
| CANONICAL_WRITE | NO |
| NUMERIC_CONFIDENCE | null |

## API_SECURITY_MATRIX

| Check | Result |
|---|---|
| NEW_SECURITY_HIGH | 0 |
| NEW_SECURITY_MEDIUM | 0 |
| NEW_WRITE_SCOPE | NO |
| NEW_AUTH_SCOPE | NO |
| PATH_TRAVERSAL | fail-closed |
| WALL_CLOCK_AS_OF | fail-closed MALFORMED_INPUT |
| CROSS_PROJECT_LEAKAGE | rejected by project-scoped claim load |

## API_PERFORMANCE_MATRIX

| Item | Result |
|---|---|
| Library dense 10k residual | MAJOR (~3.8s, 666650 candidates) |
| API added latency class | library-bound; no new pair algorithm |
| PERFORMANCE_CLASS | MAJOR (inherited residual; not downgraded) |
| NO_PAIR_DROPPED | YES |
