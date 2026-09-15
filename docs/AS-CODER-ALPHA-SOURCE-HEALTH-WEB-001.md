# AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001

Read-only Atlas Web consumer of merged `GET /v1/source-health`.

```
#/source-health?project=<id>
```

- Explicit `?project=` required. No implicit portfolio-all.
- Consumes LIVE_API via `useLiveSourceHealth` → `liveApiFetch`.
- `health_state` is an opaque string. Special-case `UNKNOWN` / `UNREADABLE`
  honestly. Do not require or special-case later freshness labels.
- SOURCE HEALTH != AUTHORITY.
- UI != CANONICAL TRUTH.
- No secret echo. Reason codes + safe explanations only.
- No write controls. No score theatre. No silent demo-as-live.

Does not replace the CLI (`atlas source-health`) or
`AS-CODER-ALPHA-SOURCE-HEALTH-API-001`. Does not merge historical `#373`.
Does not land unmerged `#414` / `#409` freshness work.

```
npm --prefix apps/web run smoke
npm --prefix apps/web run test:source-health
```
