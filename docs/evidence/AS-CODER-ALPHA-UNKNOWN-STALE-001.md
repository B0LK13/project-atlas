# AS-CODER-ALPHA-UNKNOWN-STALE-001

```
PACKAGE = AS-CODER-ALPHA-UNKNOWN-STALE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`atlas unknown` reads vault review/compile artifacts only. After a disk
edit, delete, or rename without reconnect, `rollup=clear` (or an unchanged
unknown summary) can look current.

This package compares live source fingerprints to `connect-manifest`.
Proven drift adds `source_inventory_stale` so rollup cannot stay `clear`.
Missing `source_root` or hashed inventory is `UNKNOWN`, never fabricated
`FRESH`. Synthetic D-041 fixtures without hashed inventory keep their
existing rollup and record `source_drift.status=UNKNOWN`.

Does not rewrite `connect.py` or `cli.py`. Does not import
`attention_stale`, `source_health_stale`, or `context_stale_guard`
(independent of #380/#383/#386). Does not edit `WORKLOG.md` or
`docs/backlog.md`.

```
UNKNOWN LENS != AUTHORITY
STALE INVENTORY != CURRENT UNKNOWN
UNKNOWN != FRESH
UNKNOWN != HEALTHY
CLEAR REQUIRES LIVE SOURCES WHEN INVENTORY EXISTS
```
