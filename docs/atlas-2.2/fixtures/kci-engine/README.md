# Atlas 2.2 — KCI engine fixture sketches (docs-only)

Status: **PREP ONLY** — narrative + filename inventory only.
These files are **not** production schemas or runnable harnesses.

Package: `AS-2.2-KCI-ENGINE-PREP-001`
Plan: [`../../kci-engine/FIXTURE-PLAN.md`](../../kci-engine/FIXTURE-PLAN.md)

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`

## Purpose

Reserve Knowledge CI engine fixture family names before any 2.2 runtime
implementation opens. Payloads are intentionally absent.

## Families

| Directory (sketch) | Scenario IDs | Notes |
|---|---|---|
| `suite-smoke/` | FX-2.2-KCI-001 | Minimal suite + report shape |
| `authority-refuse/` | FX-2.2-KCI-002 | Promote / silent-winner refuse |
| `conflict-visibility/` | FX-2.2-KCI-003 | Conflict unit outcomes |
| `provenance-gate/` | FX-2.2-KCI-004 | Incomplete lineage fail-closed |
| `determinism-replay/` | FX-2.2-KCI-005 | Report digest stability |
| `evidence-class-wall/` | FX-2.2-KCI-006 | Fixture ≠ PILOT PASS |

## Inventory depth

| Inventory state | Meaning | Gate credit |
|---|---|---|
| reserved / sketched | this README + FIXTURE-PLAN | **none / NO** |
| payload-present | future | none |
| harness-certified | post-READY | not available |

Family directories listed above are **reserved names**; they do not exist and
must not be interpreted as coverage.

## Creation policy

- Do **not** add JSON/YAML payload files here until `AS-2.2-KCI-001` is
  unlocked and contract-frozen.
- Do **not** reference these paths from production code or CI.
- When promoted, fixtures move to an authorized `fixtures/atlas-2.2/` tree
  with entry-gate approval.

## Cross-references

- Architecture: [`../../kci-engine/ARCHITECTURE.md`](../../kci-engine/ARCHITECTURE.md)
- Unit-test language: [`../../kci-engine/UNIT-TEST-LANGUAGE.md`](../../kci-engine/UNIT-TEST-LANGUAGE.md)
- Package: [`../../AS-2.2-KCI-ENGINE-PREP-001.md`](../../AS-2.2-KCI-ENGINE-PREP-001.md)
- Baseline: `docs/AS-2.0-KCI-001.md`, `docs/AS-2.0-KCI-HARNESS-001.md`
