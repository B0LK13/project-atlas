# AS-CODER-ALPHA-INBOX-LIST-001

Read-only project-scoped Knowledge Inbox list reconstructed on current main
from historical #368 semantics. Historical #368 is a semantic reference only.

```
atlas inbox list --vault <dir> --project <id> [--status ...] [--limit N] [--json]
```

- Project scope required. No implicit portfolio-all.
- INBOX != AUTHORITY. Observations, not Truth Core facts.
- Distinct from `atlas capture list` (session captures).
- No promote / write / lifecycle subcommands. Review stays on
  `atlas capture review` and Truth Core stays on `atlas review decide`.
- Layer B writes = 0. Secret-shaped summaries are redacted.
- UNKNOWN is valid when the scoped project has no inbox items.
- Receipt/capture ids are a single safe relative component. Listing never
  reads outside `generated/ops/inbox` and never echoes Layer B content.
- `--project unknown-project` is not an authoritative owner (status
  UNKNOWN / UNKNOWN_PROJECT), same family as inventory-drift.

Does not add `/v1/inbox`. Does not copy owner-held #406 or #409.
