# Future API contracts — Intelligence Wave 1 (DRAFT ONLY)

Status: design proposal. **Not registered. Not implemented.**

```
FUTURE_API_CONTRACT_READY = YES
LIVE_API_ROUTING_MUTATED = NO
```

These drafts describe read-only future surfaces. They must not be added
to `api_server.py`, `web_api/`, or CLI in this wave.

Truth boundary for every future response:

```
DERIVED_INTELLIGENCE_IS_AUTHORITY = NO
```

## GET /v1/intelligence/evidence

Request:

```json
{
  "vault": "<vault-root>",
  "project_id": "harbor-api",
  "claim_id": "claim-a",
  "as_of_valid_time": "2026-01-01"
}
```

`as_of_valid_time` is optional. Wall-clock tokens (`now`, `today`) must
be rejected. `project_id` is a required scope, not a hint that may leak
other projects.

Response (200): `EvidenceAssessment` JSON as defined by
`project_atlas.intelligence.EvidenceAssessment`.

Failure: 400 invalid as-of; 404 unknown claim in project; never 200 with
an invented HIGH confidence.

## GET /v1/intelligence/conflicts

Request:

```json
{
  "vault": "<vault-root>",
  "project_id": "harbor-api",
  "as_of_valid_time": "2026-01-01"
}
```

Response (200):

```json
{
  "project_id": "harbor-api",
  "truth_boundary": "CONTRADICTION CANDIDATE ≠ PROVEN FALSEHOOD / ≠ AUTO-RESOLUTION / ≠ AUTHORITY",
  "candidates": ["<ContradictionCandidate>", "..."]
}
```

Must not auto-resolve or omit UNKNOWN-honest empty lists.

## GET /v1/project-state

Request:

```json
{
  "vault": "<vault-root>",
  "project_id": "harbor-api",
  "as_of_valid_time": "2026-01-01"
}
```

Response (200): `DerivedProjectState` JSON.

Empty projects return UNKNOWN facts, never a healthy status.

## Non-goals for this draft

- Write verbs
- Auth-scope expansion
- Web route registration
- Promotion of derived results into Layer B
