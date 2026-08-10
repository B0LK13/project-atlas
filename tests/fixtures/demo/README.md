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
| `estate/harbor-api/` | `harbor-api` | Conflicting PostgreSQL major (docs 15 vs runtime 16); stale superseded ADR |
| `estate/harbor-portal/` | `harbor-portal` | Cross-project dependency on `harbor-api` |
| `estate/harbor-ops/` | `harbor-ops` | Explicit **unknown** operational fields |

## Non-claims

- Markers here are **fixture-only**.
- Do not copy `.atlas-project.yaml` into real projects to fake pilot status.
- Do not set `AUTHENTIC_ESTATE_ROOT` from this tree.
- Graph edges derived later are projections, not Layer B authority.

## Operator entry

See [`docs/demo/README.md`](../../../docs/demo/README.md) and
[`scripts/demo.ps1`](../../../scripts/demo.ps1).
