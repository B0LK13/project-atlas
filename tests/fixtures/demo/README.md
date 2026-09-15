# DEMO_FIXTURE corpus

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> Package root: `tests/fixtures/demo/`
> Discover / ingest root (normative DEMO_FIXTURE): `tests/fixtures/demo/estate/`
>
> Package: `AS-DEMO-2.1-001` · Status: `TECHNICAL_PREVIEW`

## What this is

A synthetic, repository-native demonstration estate (3 projects) for the
Atlas Technical Preview. It is **not** an authentic customer/project estate
and must never be cited as release certification evidence.

`ATLAS_DEMO_MODE=fixture` operators must point `atlas discover --source` at
**`estate/`** (not this README’s parent alone), so packaging docs are not
ingested as an `unknown-project`.

## Projects (under `estate/`)

| Directory | ID | Story role |
|---|---|---|
| `estate/harbor-api/` | `harbor-api` | Conflicting PostgreSQL major (docs 15 vs runtime 16); stale superseded ADR; bitemporal Time Machine states |
| `estate/harbor-portal/` | `harbor-portal` | Cross-project dependency on `harbor-api` |
| `estate/harbor-ops/` | `harbor-ops` | Explicit **unknown** operational fields |

## Golden demo states (AS-DEMO-2.2-001)

Two golden runtime states are produced by the **normal pipeline** (`init` ->
`discover` -> `ingest` -> `build-indexes` -> `build-portfolio`) from real Atlas
production contracts — no mock/hand-authored truth. See the acceptance test
`tests/integration/test_as_demo_2_2_golden_fixture.py` (and its mutation
proofs).

**Conflict** — `harbor-api/docs/datastore-architecture.md` (PostgreSQL 15) and
`harbor-api/src/datastore-runtime.md` (PostgreSQL 16) share
`semantic_subject: harbor-api-datastore` and the `runtime` field, so the
knowledge compiler emits one genuine unresolved conflict. `atlas ask2` returns
`status = conflict` with `ANSWER = null` (Atlas never picks a winner).

**Time Machine** — the two datastore documents carry document-declared
valid-time (`timestamp: 2024-01-15` and `2024-08-20`). `build-portfolio` derives
`generated/ops/bitemporal/harbor-api-validity-catalog.json` (AS-2.0-TEMPORAL-001)
which `atlas kdiff` consumes. `harbor-api/docs/audit-logging.md`
(`2024-08-20`) is a single-claim subject that appears only after its valid-time.

Golden handoff pins:

| Pin | Value |
|---|---|
| `DEMO_PROJECT_ID` | `harbor-api` |
| `KNOWN_QUESTION` | `audit logging` (status `known`, evidence > 0) |
| `UNKNOWN_QUESTION` | `kubernetes gpu quota autoscaling` (status `unknown`, evidence 0) |
| `CONFLICT_QUESTION` | `postgresql` (status `conflict`, no invented winner) |
| `KDIFF_SUBJECT` | `doc:harbor-api-datastore` |
| `KDIFF_FIELD` | `runtime` |
| `T1` / `T2` | `2024-03-01` / `2024-10-01` |
| `T1_EXPECTED_VALUE` / `T2_EXPECTED_VALUE` | `PostgreSQL 15` / `PostgreSQL 16` |
| `EXPECTED_DIFF_CLASS` | `value_changed` (datastore) + `added` (`doc:harbor-api-audit-logging`) |

Demonstrate the Time Machine with:

```bash
atlas kdiff --vault <vault> --project harbor-api --as-of 2024-03-01   # -> PostgreSQL 15
atlas kdiff --vault <vault> --project harbor-api --as-of 2024-10-01   # -> PostgreSQL 16
atlas kdiff --vault <vault> --project harbor-api --from 2024-03-01 --to 2024-10-01
```

## Non-claims

- Markers here are **fixture-only**.
- Do not copy `.atlas-project.yaml` into real projects to fake pilot status.
- Do not set `AUTHENTIC_ESTATE_ROOT` from this tree.
- Graph edges derived later are projections, not Layer B authority.

## Operator entry

See [`docs/demo/README.md`](../../../docs/demo/README.md) and
[`scripts/demo.ps1`](../../../scripts/demo.ps1).
