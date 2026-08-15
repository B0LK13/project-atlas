# AS-CODER-ALPHA-STATE-STALE-001

```
PACKAGE = AS-CODER-ALPHA-STATE-STALE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`atlas state` reads vault review/compile artifacts only. After a disk
edit, delete, or rename without reconnect, `rollup=stable` (or an
unchanged state summary) can look current.

This package compares live source fingerprints to `connect-manifest`.
Proven drift stamps `honesty.source_inventory_stale` and prevents
`rollup=stable`. Missing `source_root` or hashed inventory is `UNKNOWN`,
never fabricated `FRESH`. Synthetic D-041 fixtures without hashed
inventory keep their existing rollup.

Does not rewrite `connect.py` or `cli.py`. Does not import
`unknown_stale`, `attention_stale`, or `context_stale_guard`
(independent of #386/#387). Does not edit `WORKLOG.md` or
`docs/backlog.md`.

```
STATE LENS != AUTHORITY
STALE INVENTORY != CURRENT STATE
UNKNOWN != FRESH
STABLE REQUIRES LIVE SOURCES WHEN INVENTORY EXISTS
```
