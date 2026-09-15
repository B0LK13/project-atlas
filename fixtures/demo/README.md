# DEMO_FIXTURE — hero estate (`fixtures/demo`)

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> Package: `AS-DEMO-2.1-001` · Worker: hero scenario (`feat/as-demo-2.1-hero-fixture`)
> Status: `TECHNICAL_PREVIEW` · Class: `DEMO_FIXTURE`

## Honesty banner

```text
DEMO_FIXTURE
DEMO ≠ AUTHENTIC PILOT
DEMO ≠ RELEASE EVIDENCE
DEMO ≠ AUTHENTIC ESTATE
PILOT remains DORMANT_BLOCKED until AUTHENTIC_ESTATE_ROOT_AVAILABLE
ATLAS_2_1_RELEASE_CERTIFIED = NO
```

## Layout

| Path | Purpose |
|---|---|
| `estate/` | Discover root — three synthetic projects only |
| `story/` | Human/operator narrative + expected outcomes (not discovered) |
| `README.md` | This index |

## Estate projects

| Project | Role |
|---|---|
| `estate/project-a/` | Docs claim **PostgreSQL 15**; implementation claims **PostgreSQL 16** (conflict) |
| `estate/project-b/` | Declares `requires: project-a` (cross-project dependency) |
| `estate/project-c/` | Stale superseded decision + explicit **unknown** fields |

Claim lines use Atlas-recognized extractors (`Deployment:` / `requires:`) so
ingest produces real conflict + dependency records — not prose-only hints.

## Discover / Mode A

```powershell
$env:ATLAS_DEMO_MODE = "fixture"
$env:ATLAS_DEMO_FIXTURE = (Resolve-Path "fixtures\demo\estate").Path
# Never set AUTHENTIC_ESTATE_ROOT from this corpus.

atlas discover --source fixtures/demo/estate --output .tmp/demo-manifest.json
```

## Path coordination (D01 / siblings)

| Surface | Owner | Notes |
|---|---|---|
| `docs/demo/**` | D01 (#182) | Docs / quickstart / script — **do not dual-write** |
| `tests/fixtures/demo/**` | D01 (#182) | Harbor-named estate (prose docs) — **leave locked** |
| `scripts/demo.ps1` | D01 (#182) | Windows launcher — do not dual-write |
| **`fixtures/demo/**`** | **This PR (hero)** | Claim-extractable Project A/B/C story (Postgres 15↔16) |

D01 harbor corpus and this hero corpus are complementary: same narrative roles,
different paths. Prefer **this** tree when operators need a machine-detectable
deployment conflict (`Deployment: PostgreSQL 15` vs `16`).

## Non-claims

- Markers here are **fixture-only**.
- Do not copy `.atlas-project.yaml` into real projects to fake pilot status.
- Do not cite this corpus as `v2.1.0` / authentic-pilot evidence.
- Atlas must **not** fabricate a Postgres winner without authority evidence.

## Story pack

See [`story/HERO-SCENARIO.md`](./story/HERO-SCENARIO.md) and
[`story/EXPECTED-OUTCOMES.json`](./story/EXPECTED-OUTCOMES.json).
