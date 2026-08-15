# AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001

Productize `GET /v1/source-health?project=<id>` in Atlas Web.

Depends on `#367` (`AS-CODER-ALPHA-SOURCE-HEALTH-API-001`), which is on `main`.

## Surface

- Route: `/#/source-health?project=<id>`
- Hook: `apps/web/src/hooks/useLiveSourceHealth.ts`
- Page: `apps/web/src/pages/production/SourceHealthPage.tsx`

## Contract

- Explicit project scope. No implicit portfolio-all. No invented default project.
- Consume LIVE_API `GET /v1/source-health?project=` only.
- Show `reason_code` plus the canned safe `human_explanation`.
- No secret content. No raw secret echo.
- UNKNOWN remains UNKNOWN. UNREADABLE is not healthy.
- SOURCE HEALTH != AUTHORITY. UI != CANONICAL.
- Degraded / unavailable LIVE_API state is visible.
- DEMO_ONLY is an isolated stub and is never labelled live.
- No silent demo fallback presented as live.
- No score theatre (counts are inventory, not scores).
- No write controls (no accept / reject / promote).

Does not replace `#364` What Next, `#365` MCP brief, `#366` Obsidian-002, or `#367` source-health API.
