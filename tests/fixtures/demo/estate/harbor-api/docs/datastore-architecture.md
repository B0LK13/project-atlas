# Datastore engine — architecture decision (2024 H1)

> DEMO FIXTURE — NOT AUTHENTIC PILOT — NOT RELEASE EVIDENCE

The Harbor API architecture of record pins the relational datastore engine.
This record and the deployed runtime pin (`../src/datastore-runtime.md`)
describe the **same** datastore subject and the **same** field, so Atlas can
surface the intentional version disagreement as an unresolved conflict.

semantic_subject: harbor-api-datastore
timestamp: 2024-01-15

## Datastore

runtime: PostgreSQL 15
