# AS-CODER-ALPHA-OVERVIEW-STALE-001

```
PACKAGE = AS-CODER-ALPHA-OVERVIEW-STALE-001
HISTORICAL_BASE = 32c992894d7cabe58dd4b965585093fe6d308458
RECONCILED_BASE = 5b7f564863d09d82fb7977cfc495f5a2b5124f6b
RECONCILED_BASE_TREE = a80248c7d240613f8f188d78a0142bb849e553c6
OWNER_HELD = NO
CERTIFICATION = NOT_GRANTED
MERGE_AUTHORIZATION = NOT_GRANTED
SELF_REVIEW != INDEPENDENT_IV
```

`atlas overview` reads vault Layer A imported evidence + Layer B project
notes only. After a disk edit, delete, or rename without reconnect,
`status=derived` (or an unchanged README blurb) can look current.

This package compares live source fingerprints to `connect-manifest`.
Proven drift adds `source_inventory_stale` so a derived overview cannot
look current. Missing `source_root` or hashed inventory is `UNKNOWN`,
never fabricated `FRESH`. Synthetic fixtures without hashed inventory
keep their existing derived/unknown status and record
`source_drift.status=UNKNOWN`.

Does not rewrite `connect.py` or `cli.py`. Does not import
`attention_stale`, `unknown_stale`, `state_stale`, or
`source_health_stale` (independent of #386/#387/#388/#383). Does not
edit `WORKLOG.md` or `docs/backlog.md`.

```
OVERVIEW LENS != AUTHORITY
STALE INVENTORY != CURRENT OVERVIEW
UNKNOWN != FRESH
UNKNOWN != HEALTHY
DERIVED REQUIRES LIVE SOURCES WHEN INVENTORY EXISTS
```
