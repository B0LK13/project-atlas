# AS-CODER-ALPHA-SOURCE-HEALTH-API-001

Read-only LIVE_API projection of `atlas source-health`.

```
GET /v1/source-health?project=<id>
```

- Project scope required. No implicit portfolio-all.
- SOURCE HEALTH != AUTHORITY.
- No Layer B writes.
- Same project-token boundary as `/v1/conflicts` (`^[a-z][a-z0-9-]{0,63}$`).

Does not replace `#364` What Next, `#365` MCP brief, or `#366` Obsidian-002.
