# Atlas 3.0 — Foundation threat model

| Field | Value |
|---|---|
| Directive | D-193 §13 |
| Status | **REVIEWED FOUNDATION MODEL** |
| Runtime | `src/project_atlas/atlas3/security.py` (catalog, not a scanner) |

## Threats and required behavior

| Threat | Required behavior |
|---|---|
| Provider spoofing | Honest `import_mode` + capability state; metadata ≠ authority |
| Forged owner decisions | `FALSE_OWNER_DECISION` without `owner_origin` |
| Cross-project contamination | Fail-closed project routing; zero leak |
| Secret ingestion | `scan_text`; reject; no secret echo |
| Prompt injection | Stay non-canonical; never auto-promote |
| Event replay | Idempotent same `event_id` |
| Duplicate events | Ledger replay, not a second fact |
| Timestamp spoofing | Observation only; cannot beat stronger evidence |
| Malicious attachments | Source safety; quarantine |
| Stale-memory poisoning | Freshness states; Start `CURRENT` refuses stale-as-truth |
| Agent self-certification | `MODEL CLAIM != PROOF` |
| Authority escalation | Inbox/ledger/twin remain non-canonical |

## Demo isolation

Atlas 3 must not mutate certified 2.x demo surfaces while
`FULL_LIVE_DEMO_READY = NO`. Overlap: demo closure wins.

## Honesty

This document is a threat model, not an external security certification.
`EXTERNAL_SECURITY_REVALIDATION_REQUIRED = YES`.
