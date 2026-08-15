# AS-CODER-ALPHA-INBOX-API-001

Read-only LIVE_API projection of `list_inbox_items` (`AS-CODER-ALPHA-INBOX-LIST-001`).

```
GET /v1/inbox?project=<id>[&status=quarantined|accepted-review|rejected][&limit=N]
```

## Stacking

- `STACKED_IMPLEMENTATION_COMPLETE`
- `DEPENDENCY_PR=368`
- `OWNER_MERGE_REQUIRED=YES`
- Not merge-eligible to `main` while `#368` is unmerged.
- `#368` HEAD (immutable): `b071e0bfcb6a43a75af1faa13feec9fb5249fc18`

## Contract

- Explicit project required. No implicit portfolio-all.
- Read-only. GET only. Other methods return `405 writes-forbidden`.
- Project isolation. Orphan receipts without project identity MUST NOT leak.
- Secret-safe summaries. No raw secret echo.
- No Layer B / accept / reject / promote.
- Malformed and path-shaped tokens fail closed.
- INBOX != AUTHORITY. CAPTURE != VERIFIED FACT.
- UNKNOWN remains UNKNOWN when the project has no inbox items.
- Bounded `limit` (default 20, max 100).

Does not replace `#364` What Next, `#365` MCP brief, `#366` Obsidian-002, `#367` source-health API, or `#368` inbox list.
