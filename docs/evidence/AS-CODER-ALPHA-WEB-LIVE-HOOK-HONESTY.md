# TRUTH-UX-001 — LIVE web hook honesty

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
BRANCH: `cursor/live-hook-honesty-25b1`
BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f`

```
LIVE_FAILURE != DEMO_STUB
UI != CANONICAL_TRUTH
MERGE_AUTHORIZATION = NOT_GRANTED
```

Not #354 / #356 / #357. Does not touch Ask or Time Machine hooks.

## Defect

Several production LIVE hooks labeled HTTP/network failure as `demo_stub`.
That made an unavailable vault look like an isolated demo.

## Change

`useLiveBrief`, `useLiveKnowledge`, `useLiveGraph`, `useOpsReceipts`, and
`useEstateDiscovery` keep `demo_stub` only when `DEMO_ONLY` is set.
LIVE failures stay explicit errors with `dataSource=null`.

## Rollback

Revert this branch. No schema or vault migration.
