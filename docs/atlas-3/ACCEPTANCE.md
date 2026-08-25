# Atlas 3.0 — Program acceptance

## Honesty first

This document accepts a **program**, not a commercial release.

```text
FULL_LIVE_DEMO_READY = NO
AUTHENTIC_PILOT = NO
MERGE_AUTHORIZATION = NOT_GRANTED
DEMO != RELEASE
```

## D-191 program acceptance (inception)

| ID | Criterion | Evidence |
|---|---|---|
| A3-NS | North star exists and reuses Coder Alpha promises | `NORTH-STAR.md` |
| A3-ARCH | Architecture states reuse/new/migration/risk | `ARCHITECTURE.md` |
| A3-RM | Waves A–L recorded; first vertical named | `MASTER-ROADMAP.md` |
| A3-EPIC | Epic catalog counted | `EPICS.md` |
| A3-DAG | Dependency DAG + forbidden edges | `DEPENDENCY-DAG.md` |
| A3-MIG | 2.x artifacts remain compatible | `MIGRATION-2X-TO-3X.md` |
| A3-PX | Pulse / Start / Proof contracts | `PRODUCT-EXPERIENCE.md` |
| A3-ISO | Historical roadmaps classified, not erased | `HISTORICAL-INPUTS.md` |
| A3-RT | Isolated runtime exists under `atlas3/` | `src/project_atlas/atlas3/` |
| A3-DEMO | Certified demo surfaces not rewritten | isolation tests |

## First-vertical acceptance

| Package | Ready means | Not ready means |
|---|---|---|
| AT3-003 | Engineering events normalize to one envelope | Rewriting `EventType` enum |
| AT3-014 | Append-only project ledger under atlas3/ | Dual-write ops_events |
| AT3-015 | Pulse answers the seven questions honestly | Inventing changes |
| AT3-030 | Start requires a token budget | RAG dump |
| AT3-050 | Proof chain; model claim ≠ proven | Auto-complete from LLM text |

## D-192 acceptance (see llm-memory/ACCEPTANCE.md)

The memory feature is not complete when a transcript can be uploaded.

It is complete when all ten success criteria in D-192 §34 hold. This slice
proves the **ChatGPT export → envelope → extract → dedup → freshness → search**
path plus the multi-provider PostgreSQL fixture. Claude/Gemini native history
sync is **not** claimed.

## Fail-closed tests required

- forged owner decision
- secret-shaped conversation text
- ambiguous project routing
- missing token budget on `atlas start`
- model completion claim on `atlas proof`
- pulse on empty vault → UNKNOWN, not invented history
