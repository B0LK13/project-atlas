# AS-CODER-ALPHA-ATTENTION-STALE-001

```
PACKAGE = AS-CODER-ALPHA-ATTENTION-STALE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`atlas attention` classifies vault review/compile artifacts only. After a
disk edit, delete, or rename without reconnect, `rollup=CLEAR` can look
current.

This package compares live source fingerprints to `connect-manifest`.
Proven drift adds a `STALE` attention item so rollup cannot stay `CLEAR`.
Missing `source_root` or hashed inventory is `UNKNOWN`, never fabricated
`FRESH`. Synthetic D-041 CLEAR fixtures without hashed inventory stay
`CLEAR` and record `source_drift.status=UNKNOWN`.

Does not rewrite `connect.py` or `cli.py`. Does not import
`source_health_stale` or `context_stale_guard` (independent of #380/#383).

```
ATTENTION LENS != AUTHORITY
STALE INVENTORY != CURRENT
UNKNOWN != FRESH
CLEAR REQUIRES LIVE SOURCES WHEN INVENTORY EXISTS
```
