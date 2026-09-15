# Atlas 3 — LLM memory security

## Matrix (fail closed or quarantine)

| Case | Required behavior |
|---|---|
| Prompt injection in conversation | Stay non-canonical; never auto-promote; never become owner decision |
| Secret leakage | Reject or redact; no secret echo in receipts |
| Forged owner statement | `FALSE_OWNER_DECISION` / proposed_decision |
| Forged project id | Fail closed; no mint; no fuzzy route |
| Malformed export | Fail closed |
| Oversized export | Fail closed |
| Cross-project conversation | Fail closed or unmatched — zero leak |
| Duplicate replay | Idempotent same id |
| Provider spoof | Honest `import_mode` + capability; metadata is not authority |
| Timestamp spoof | Observation only; cannot beat stronger evidence |
| Malicious attachment | Source safety; quarantine |
| Path escape | `safe_relative_component` / vault relative writes only |
| HTML/script content | Treat as text; no execution |
| Tool-result injection | Tool refs are evidence, not truth |

## Invariants reused from 2.x

- MCP remains read-only (no memory write tool in this slice)
- Quarantine payloads stay digest-oriented where PROV already requires that
- `promote_authority` remains forbidden on inbox
- chatgpt-live production surface stays frozen
- Demo-critical modules stay untouched

## Implementer ≠ verifier

Security tests in `tests/unit/test_atlas3_memory_security_001.py` must keep
the matrix honest even if extractor heuristics expand later.
