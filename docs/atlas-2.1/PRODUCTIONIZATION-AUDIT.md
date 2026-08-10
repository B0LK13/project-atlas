# Atlas 2.1 — Productionization reality audit

| Field | Value |
|---|---|
| Package | AS-2.1-DOC-REALITY-001 |
| Tip audited | `1ac7a3f6c5b0a1bf9e4f8d2626ba1248c4877eb2` (`v2.0.0`) |
| Method | Code + tests + module docstrings — **not** package marketing names |
| Auditor | Autonomous agent under `D-PROJECT-ATLAS-2.1-PRODUCTIONIZATION-001` |

## Executive finding

Atlas 2.0 shipped a **broad contract/fixture surface** that is RELEASE CERTIFIED under an explicit fixture pilot waiver. Most “2.0 production” packages are **receipt builders / registries / catalogs**. Live HTTP, live MCP, live scheduler dispatch, real OpenAI export ingestion, L3 autonomy, and authentic estate PILOT remain **open gaps** for 2.1.

## Evidence anchors (tip)

| Surface | Evidence |
|---|---|
| Web shell | `apps/web` Vite/React; `useReadStatus` fetches `/sample-read-status.json` stub; README: “until an HTTP bridge lands” |
| Web API adapters | `project_atlas.web_api` — Python read helpers over vault paths; **no HTTP server** |
| API 2.0 | `api_surface_registry.py` — registry with `write_enabled=false`; no ASGI/WSGI app |
| MCP | `mcp_registry.py` — “no live server”; deny-by-default tool table |
| OpenAI import | `openai_importer_fixtures.py` — “no live API”; synthetic fixture under `docs/atlas-2.0/fixtures/` |
| Provider | `provider_adapters.py` — disabled-by-default; no SDK wiring |
| Scheduler | `scheduler_dry_run.py` — forbids `enable_live_dispatch` |
| Autonomy | `autonomy_levels.py` — `live_autonomy=false`; L3 `enabled=False` |
| SYNC/TWIN “production” | `sync_production.py` / `twin_production.py` — fixture `evidence_class` only; final-cert waiver pin |
| Pilot | `final_cert_pilot.py` / `docs/releases/2.0.0/PILOT-REPORT.md` — authentic=NO forever for 2.0 |

## Classification summary

See `FEATURE-MATURITY-MATRIX.md` for the full table. Headline:

| Band | Count (approx) | Examples |
|---|---|---|
| Core/1.0 live-local CLI pipeline | LIVE_PRODUCTION (local vault) | discover/ingest/validate/indexes |
| Web UI shell | PROTOTYPE / STUB data path | `apps/web` + sample JSON |
| 2.0 Wave registries/catalogs | CONTRACT_ONLY | API/MCP/UX/OBS/WEB surface catalogs |
| 2.0 fixture harnesses | FIXTURE_ONLY / DRY_RUN | OAI import, twin fixtures, scheduler dry-run, ADV cert |
| Fixture-waived “production” | BOUNDED / FIXTURE_ONLY | SYNC-001 / TWIN-001 under waiver |
| Docs / prototypes | DOCUMENTATION_ONLY / PROTOTYPE | `docs/atlas-2.0/prototypes/*` |

## Required 2.1 promotions

| Target outcome | From | To package |
|---|---|---|
| LIVE_API | API registry + web_api helpers | AS-2.1-API-SERVER-001 (+ APP-SVC) |
| WEB_DATA | sample JSON stub | AS-2.1-WEB-LIVE-001 |
| MCP_READ | MCP registry | AS-2.1-MCP-SERVER-001 |
| REAL_OPENAI_EXPORT_IMPORT | OAI fixture harness | AS-2.1-OAI-IMPORT-REAL-001 |
| LIVE_SUPERVISED_SCHEDULER | scheduler dry-run | AS-2.1-SCHED-LIVE-001 |
| L3_BOUNDED_AUTONOMY | catalog L3 disabled | wave-2+ after AUTHZ/SCHED |
| AUTHENTIC_ESTATE_PILOT=PASS | 2.0 waived authentic=NO | AS-2.1-PILOT-AUTH-001 (+ prep) |

## Honest non-claims at audit time

- Not LIVE_API / WEB_DATA / MCP_READ yet
- Not REAL_OPENAI_EXPORT_IMPORT yet
- Not LIVE_SUPERVISED_SCHEDULER yet
- Not L3_BOUNDED_AUTONOMY yet
- Not AUTHENTIC_ESTATE_PILOT=PASS
- `ATLAS_2_1_RELEASE_CERTIFIED = NO`
