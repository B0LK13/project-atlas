# AS-CODER-ALPHA-UNKNOWN-API-001

Read-only LIVE_API projection of `atlas unknown`.

```
GET /v1/unknown?project=<id>
```

- Project scope required. No implicit portfolio-all.
- UNKNOWN != HEALTHY. UNKNOWN != AUTHORITY.
- No Layer B writes. Does not materialize answer files.
- Same project-token boundary as `/v1/source-health` (`^[a-z][a-z0-9-]{0,63}$`).

Web companion: `AS-CODER-ALPHA-UNKNOWN-WEB-001` (`#/unknown`).

Does not replace `/v1/conflicts`, `/v1/intelligence/conflicts`, or D-149.
Does not claim MCP (`atlas.unknown.read` remains on owner-held #479).
