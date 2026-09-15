# Harbor API — Runtime pin

> DEMO FIXTURE — NOT AUTHENTIC PILOT — NOT RELEASE EVIDENCE

## Implementation evidence

The deployed runtime image and local `docker-compose` pin the database to
**PostgreSQL 16**.

## Conflict note (intentional)

Architecture / ADR documentation in this fixture claim PostgreSQL 15.
This runtime note claims PostgreSQL 16.

Atlas must surface a **conflict** (or refuse false certainty) rather than
silently picking a winner without authority evidence.
