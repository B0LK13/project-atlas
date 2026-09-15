# Atlas 2.1 — Live productionization

| Field | Value |
|---|---|
| Directive | `D-PROJECT-ATLAS-2.1-PRODUCTIONIZATION-001` |
| Baseline tip | `1ac7a3f6c5b0a1bf9e4f8d2626ba1248c4877eb2` (= `v2.0.0`) |
| Immutable 2.0 freeze | MAIN `045b7d7` / TREE `2dbbfbf` / tag `v2.0.0` |
| Stop condition | **PROJECT ATLAS 2.1 — LIVE PRODUCTIONIZATION COMPLETE · RELEASE CERTIFIED** (`v2.1.0`) |
| Evidence | `D:\project-atlas-orphans\atlas-2.1-productionization-001\` |

## Purpose

Promote Atlas 2.0 **certified contracts / fixtures / dry-runs** into **live, supervised production** surfaces without rewriting 2.0 history.

Required release outcomes (unless architecture-deferred with explicit evidence):

- `LIVE_API` / `WEB_DATA` / `MCP_READ`
- `REAL_OPENAI_EXPORT_IMPORT`
- `LIVE_SUPERVISED_SCHEDULER`
- `L3_BOUNDED_AUTONOMY`
- `AUTHENTIC_ESTATE_PILOT=PASS`
- `CRITICAL/HIGH=0`

Authentic estate PILOT is **2.1 release-critical**. Do **not** default to a fixture waiver.

## Tree

| Doc | Role |
|---|---|
| `README.md` | This index |
| `CHARTER.md` | Non-goals, invariants, 2.0 boundary |
| `PRODUCTIONIZATION-AUDIT.md` | Code-backed reality audit (§4–6) |
| `FEATURE-MATURITY-MATRIX.md` | Capability × maturity class |
| `KNOWN-GAPS.md` | Gaps A–K revalidated at tip |
| `DAG.md` | Package dependency order |
| `PACKAGE-BOARD.md` | Wave status / sole-writers |
| `THREAT-MODEL-DELTA.md` | Live-surface threat delta vs 2.0 |

## Invariants (carry forward)

- UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy
- 1.0 wins conflicts via compatibility anchor
- No silent authority promotion from live adapters
- Secrets: metadata-only findings; never log matched secrets
