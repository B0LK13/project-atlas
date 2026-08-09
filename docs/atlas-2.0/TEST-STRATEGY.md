# PREP — Test strategy (Atlas 2.0 prep)

Status: **PREP ONLY**.

## Layers

| Layer | Scope | When |
|---|---|---|
| Unit | Contract sketches / doc presence / non-claims | now (docs/fixtures) |
| Fixture integration | 1.0 pipeline + ADV/SEC matrices | now (1.0) |
| Estate pilot | authentic roots only | owner-gated |
| 2.0 package | after READY + freeze | blocked |

## Required negative cases (inventory)

- Ambiguous federation identity → quarantine
- Provider output without provenance → reject
- UI attempting canonical write → forbidden
- Empty/home/FS-root sync scan → refuse
- False WEB ACCEPTED stamp without governor → reject

## Explicit

No 2.0 production test harness claiming READY from this document.
