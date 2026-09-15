# Future Web data contracts — Intelligence Wave 1 (DRAFT ONLY)

Status: conceptual data contracts. **No Web mutation in this wave.**

```
FUTURE_WEB_DATA_CONTRACT_READY = YES
WEB_CODE_MUTATED = NO
```

Do not add components, routes, or navigation. These shapes exist so a
later isolated Web lane can bind to the backend library without
redesigning truth boundaries.

## Project Intelligence

Top-level page model:

```json
{
  "project_id": "harbor-api",
  "as_of_valid_time": "2026-01-01",
  "truth_boundary": "DERIVED INTELLIGENCE ≠ AUTHORITY",
  "state": "<DerivedProjectState>",
  "attention": ["<AttentionCandidate>"]
}
```

## Contradictions

```json
{
  "project_id": "harbor-api",
  "candidates": ["<ContradictionCandidate>"],
  "auto_resolve": false,
  "empty_means": "no-candidates-not-proven-consistency"
}
```

## Evidence

```json
{
  "claim_id": "claim-a",
  "assessment": "<EvidenceAssessment>",
  "confidence_is_probability": false
}
```

## Project State

Reuse `DerivedProjectState`. UI labels must preserve:

- UNKNOWN ≠ false
- CONTESTED ≠ resolved
- STALE ≠ invalid
- NO_DATA ≠ healthy

## Attention

Reuse `AttentionCandidate`. Every chip/row must show `reason`.
No red/green health glyph unless a claim value itself supplies that
word.

## Isolation reminder

Do not touch:

- `apps/web/src/App.tsx`
- `apps/web/src/components/ProdNav.tsx`
- `apps/web/src/pages/production/KnowledgePage.tsx`
- Time Machine or Roadmap shared surfaces
