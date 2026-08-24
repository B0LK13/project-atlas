# AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001

Dedicated Web hash route for the existing source-health LIVE_API.

```
#/source-health?project=<id>
```

Consumes `GET /v1/source-health?project=<id>` (AS-CODER-ALPHA-SOURCE-HEALTH-API-001).

- Project scope is explicit (`?project=`). No implicit portfolio-all.
- SOURCE HEALTH != AUTHORITY. UI != canonical. UNKNOWN != healthy.
- DEMO_ONLY stays an isolated stub (`health_state=UNKNOWN`); it does not invent CLEAR.
- No Layer B writes. No secret echo.

Does not replace `#477` D-149, `#478` inbox/overview APIs, `#479` unknown/changed APIs,
or the CLI `atlas source-health` lens.
