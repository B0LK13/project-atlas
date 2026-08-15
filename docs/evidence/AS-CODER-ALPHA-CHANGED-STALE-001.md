# AS-CODER-ALPHA-CHANGED-STALE-001

```
PACKAGE = AS-CODER-ALPHA-CHANGED-STALE-001
STACKED_ON = 383
BASE_BRANCH = cursor/source-health-stale-001-315e
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

What Changed diffs last-connect inventory, not live disk. After a disk
edit without reconnect, `rollup=unchanged` can look current.

This successor reuses #383 `evaluate_source_inventory_drift` and stamps
`honesty.live_inventory_stale`. It does not invent a change history.

Does not rewrite `connect.py` or `cli.py`.

```
WHAT CHANGED != AUTHORITY
UNCHANGED != CURRENT AFTER LIVE DRIFT
```
