# Runtime


semantic_subject: harbor-database
semantic_kind: doc
timestamp: 2024-08-20

Deployment: PostgreSQL 16

## Implementation evidence

The deployed runtime image and local compose pin claim PostgreSQL 16.

## Conflict note (intentional)

`ARCHITECTURE.md` and ADR documentation claim PostgreSQL 15.
This runtime note claims PostgreSQL 16 on the same semantic subject.

Atlas must surface a conflict (or refuse false certainty) rather than
silently picking a winner without authority evidence.
