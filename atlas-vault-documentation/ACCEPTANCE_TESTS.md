# Acceptance Tests

## AS-001 Skill discovery

The directory contains readable `SKILL.md` and `MDA-STANDARD.md`.

## AS-002 Immediate raw capture

A valid command atomically writes one date-partitioned source event.

## AS-003 Stable event ID

An explicit event ID remains unchanged through validation and normalization.

## AS-004 No silent overwrite

A different payload under an existing event ID fails without modifying the original.

## AS-005 Secret redaction

Fixture API keys and tokens do not appear in persisted Markdown or output.

## AS-006 Spool fallback

When vault use is impossible and spool is supplied, capture writes to `.atlas-spool` and marks synchronization pending.

## AS-007 Strict spool gate

Documentation check exits non-zero when pending spool events exist in strict mode.

## AS-008 Controlled taxonomy

Unsupported event kinds fail validation or are explicitly marked for review.

## AS-009 Raw immutability

Normalization never uses in-place mode on raw evidence.

## AS-010 Normalized provenance

The normalized event references its raw source.

## AS-011 Conservative status

Unexecuted tests cannot become completed-and-validated claims.

## AS-012 Exact validation retention

Exact pass/fail counts and command text survive normalization.

## AS-013 Project log routing

A routed event creates exactly one linked project-log entry.

## AS-014 Idempotent routing

Routing the same event twice does not duplicate the log entry.

## AS-015 Protected human content

Routing preserves human regions byte-for-byte.

## AS-016 Receipt gate

Clean completion requires a receipt with actual event, source, update, validation, and sync fields.

## AS-017 Multi-agent uniqueness

Two agents in one work package produce distinct event IDs.

## AS-018 Path safety

Traversal input cannot write outside vault or spool roots.

## AS-019 Provider degradation

Provider failure leaves raw evidence intact and normalization pending.

## AS-020 End-to-end traceability

One fixture event is traceable from raw source through normalized event, project log, work package, and receipt.
