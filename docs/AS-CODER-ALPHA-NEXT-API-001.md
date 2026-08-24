# AS-CODER-ALPHA-NEXT-API-001

Read-only LIVE_API projection of `atlas next` / `build_next_lens`.

```
GET /v1/next?project=<id>
```

- Project scope required. No implicit portfolio-all.
- NEXT != AUTHORITY. NEXT != COMMAND.
- No Layer B writes. Uses derive, never `materialize_next_lenses`.
- Same project-token boundary as `/v1/source-health` (`^[a-z][a-z0-9-]{0,63}$`).
- Independent of `AS-2.0-NEXT-001` / Wave 15-16 intelligence.
- Does not resurrect stale draft `#406` as merge authority.

Companion surfaces on this package:

- `AS-CODER-ALPHA-NEXT-WEB-001` — Web `#/next`
- `AS-CODER-ALPHA-NEXT-MCP-001` — zero-arg `atlas.next.read`
