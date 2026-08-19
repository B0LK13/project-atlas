# AS-CODER-ALPHA-ARCHITECTURE-STALE-001

```
PACKAGE = AS-CODER-ALPHA-ARCHITECTURE-STALE-001
BASE = 5b7f564863d09d82fb7977cfc495f5a2b5124f6b
BASE_TREE = a80248c7d240613f8f188d78a0142bb849e553c6
CERTIFICATION = NOT_GRANTED
MERGE_AUTHORIZATION = NOT_GRANTED
SELF_REVIEW != INDEPENDENT_IV
```

`atlas` architecture lenses read imported architecture-bearing documents
selected through `connect-manifest`. After a disk edit, delete, or rename
without reconnect, `status=derived` can look current.

This package compares live architecture-bearing source fingerprints to
`connect-manifest`. Proven drift adds `source_inventory_stale` so a derived
architecture lens cannot look current. Missing `source_root` or hashed
architecture inventory is `UNKNOWN`, never fabricated `FRESH`. README-only
edits do not stale architecture.

Independent of #389 overview_stale. Does not rewrite `connect.py` or
`cli.py`. Does not edit `WORKLOG.md` or `docs/backlog.md`.

```
ARCHITECTURE LENS != AUTHORITY
STALE INVENTORY != CURRENT ARCHITECTURE
UNKNOWN != FRESH
UNKNOWN != HEALTHY
README != ARCHITECTURE AUTHORITY
```
