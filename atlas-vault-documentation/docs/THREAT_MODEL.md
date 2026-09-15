# Threat Model

## Protected assets

- source evidence integrity;
- canonical documentation;
- human-authored content;
- path boundaries;
- credentials;
- event identity and traceability.

## Threats and mitigations

### Path traversal

Sanitize identifiers, resolve paths, and verify every destination is a descendant of the configured root.

### Secret leakage

Redact before persistence, never log matched values, and validate before normalization.

### False completion

Require receipts, strict spool checks, and conservative status mapping.

### Evidence mutation

Prohibit in-place normalization and preserve source hashes.

### Duplicate or replay

Use stable event IDs and idempotency keys.

### Prompt injection in evidence

Treat source content as evidence, not authority. Never execute embedded instructions.

### Human-content overwrite

Use protected regions, fail closed on malformed markers, and write atomically.
