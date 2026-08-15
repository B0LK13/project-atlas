# Future Web data contracts — Intelligence Waves 2–5 (DRAFT ONLY)

Status: typed backend/UI shapes. **No Web mutation in this wave.**

```
#354_WEB_LANE = ACTIVE_OR_UNSEALED
WEB_CODE_MUTATED = NO
NAVIGATION_MUTATED = NO
```

Do not add components, routes, or navigation while any final-train Web
lane remains open.

## Project Intelligence

Reuse Wave 1 `Project Intelligence` page model and add:

```json
{
  "explain": ["<EvidenceTrace>"],
  "gaps": ["<EvidenceGap>"],
  "changes": ["<SemanticChange>"],
  "deltas": ["<ValueDelta>"],
  "risks": ["<RiskSignal>"]
}
```

## Evidence Explorer

```json
{
  "project_id": "harbor-api",
  "assessments": ["<EvidenceAssessment>"],
  "confidence_is_probability": false,
  "unknown_is_valid": true
}
```

## Contradictions

Reuse Wave 1 contradictions model. Candidates are not proven falsehoods.

## Project State

Reuse `DerivedProjectState`. Labels:

- UNKNOWN ≠ false
- CONTESTED ≠ resolved
- STALE ≠ invalid
- NO_DATA ≠ healthy

## Attention

Reuse `RiskSignal` / `AttentionCandidate`. Every row shows `reason`.
No opaque score. Attention ≠ failure.

## Portfolio Intelligence

```json
{
  "portfolio": "<PortfolioState>",
  "dependencies": ["<PortfolioDependency>"],
  "attention": ["<PortfolioAttentionEntry>"],
  "numeric_priority": null,
  "inferred_dependencies": false
}
```

## Isolation reminder

Do not touch `apps/web/**`, `api_server.py`, or shared navigation.
