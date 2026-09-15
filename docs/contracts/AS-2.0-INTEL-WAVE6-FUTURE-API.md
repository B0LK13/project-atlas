# Future API contracts — Intelligence Waves 2–5 (DRAFT ONLY)

Status: design proposal. **Not registered. Not implemented.**

```
#354_FINAL_TRAIN = OPEN
LIVE_API_ROUTING_MUTATED = NO
NEW_AUTH_SCOPE = NO
WRITE_VERBS = NO
```

Register these routes only after `#354` is fully merged and sealed.
Until then this file is the contract, not an implementation license.

Truth boundary for every future response:

```
DERIVED_INTELLIGENCE_IS_AUTHORITY = NO
CANONICAL_WRITE = NO
NEXT_ACTION_CANDIDATE_IS_COMMAND = NO
```

All methods are GET. Query parameters only. No POST body.

## GET /v1/intelligence/evidence

See `AS-2.0-INTEL-WAVE1-FUTURE-API.md`. Library:
`query_intelligence(kind=evidence)`.

## GET /v1/intelligence/conflicts

See Wave 1 draft. Library: `query_intelligence(kind=conflicts)`.

## GET /v1/intelligence/explain

Query: `project_id` (required), optional `subject`, `field`, `claim_id`,
`as_of_valid_time`.

Response: `EvidenceTrace` JSON from `explain_why`.

Wall-clock `as_of` → 400. Empty scope → UNKNOWN trace, not invented
confidence.

## GET /v1/intelligence/gaps

Query: same project scope.

Response: `EvidenceGap[]`. Distinguishes
`unknown-from-no-evidence` / `contested` / `stale` / `limited`.

## GET /v1/project-state

See Wave 1 draft. Library: `synthesize_project_state`.

## GET /v1/project-attention

Query: `project_id` (required), optional `as_of_valid_time`.

Response: `RiskSignal[]` from `detect_risk_signals`.

`RISK_SIGNAL_IS_FACT = NO`. Empty project → unknown-is-not-safe signals,
never healthy.

## GET /v1/portfolio-state

Query: repeated `project_id` or vault-wide listing of known project ids.

Response: `PortfolioState` plus optional `PortfolioDependency[]` and
`PortfolioAttentionEntry[]`.

Must reject cross-project leakage. No numeric priority score.

## GET /v1/intelligence/next-actions

Optional later. Response: `NextActionCandidate[]` with
`is_command=false` and `executable=false`. Do not expose an execute
verb.

## Non-goals

- POST / write scope
- Auth-scope expansion
- Web route registration
- Binding into `api_server.py` while `#354` remains open
