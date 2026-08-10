# Live Reality Gap collectors — contract stubs index

Package: **AS-2.2-REALITY-LIVE-001** (base prep) + **AS-2.2-REALITY-LIVE-DEEPEN-PREP-001** (deepen).

Status: **PREP ONLY**. JSON files under `docs/atlas-2.2/contracts/reality-live/` and
this deepen tree are **documentation stubs**, not installed package schemas.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Base stubs (peer — do not relocate)

| Stub file | Artifact | Owner |
|---|---|---|
| `reality-live-planes.schema.draft.json` | Four-plane catalog | AS-2.2-REALITY-LIVE-001 |
| `reality-live-gap-report.schema.draft.json` | Aggregated gap report | AS-2.2-REALITY-LIVE-001 |

## Deepen stub (this tree)

| Stub file | Artifact | Axis |
|---|---|---|
| `reality-live-forbidden-action.schema.json` | Fail-closed action proposal | Forbidden ops |

## FR stubs (planning IDs only)

| ID | Requirement stub |
|---|---|
| FR-2.2-RL-001 | Collectors are read-only; never write Layer A/B |
| FR-2.2-RL-002 | Conversational plane never sole certifier for `LIVE_PRODUCTION` |
| FR-2.2-RL-003 | Aggregator emits derived gap report with `authority.level=derived` |
| FR-2.2-RL-004 | `pilot_roots=0` and `invent_pilot_roots=false` on all plane reports |
| FR-2.2-RL-005 | Missing evidence maps to `UNKNOWN`, not invented healthy class |
| NFR-2.2-RL-001 | Deterministic serialization (`sort_keys`, no `generated.at`) |
| NFR-2.2-RL-002 | Prep stubs must not alter 2.0/2.1 runtime defaults |

## Forbidden until unlock

- Importing draft schemas from production modules
- Referencing them from `.github/workflows/ci.yml` as required release gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture gap report alone
- Writing Layer B notes from collector observations
