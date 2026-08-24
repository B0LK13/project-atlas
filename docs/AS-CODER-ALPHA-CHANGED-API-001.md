# AS-CODER-ALPHA-CHANGED-API-001

Read-only LIVE_API projection of `atlas changed`.

```
GET /v1/changed?project=<id>
```

- Project scope required. No implicit portfolio-all.
- CHANGED != KDIFF. CHANGED != AUTHORITY.
- Missing connect inventory is UNKNOWN history, never invented UNCHANGED.
- No Layer B writes. Does not rotate connect inventories or write answer files.
- Same project-token boundary as `/v1/source-health` (`^[a-z][a-z0-9-]{0,63}$`).

Web companion: `AS-CODER-ALPHA-CHANGED-WEB-001` (`#/changed`).

Does not replace `/v1/kdiff` or owner-held `#406` / `#481` What Next.
Does not claim MCP (`atlas.changed.read` remains on owner-held #479).
