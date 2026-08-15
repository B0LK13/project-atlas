# AS-CODER-ALPHA-SOURCE-HEALTH-STALE-001

```
PACKAGE = AS-CODER-ALPHA-SOURCE-HEALTH-STALE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`atlas source-health` reads vault artifacts. After a disk edit without
reconnect it can still report `CLEAR`. This package rehashes active
connect-manifest sources and overrides `CLEAR` to `STALE` (or `UNKNOWN`
when `source_root` cannot be verified).

Independent of #380 / #381. Does not rewrite `connect.py` or `cli.py`.
Does not edit `apps/web/**`.

```
SOURCE HEALTH != AUTHORITY
STALE != CLEAR
UNKNOWN != HEALTHY
```
