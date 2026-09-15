# D-102 — PR #358 exact-main refresh

```
DIRECTIVE = D-PROJECT-ATLAS-CLOUD-D102-PR358-EXACT-MAIN-REFRESH-AND-D100-RECONCILIATION
PR = 358
BRANCH = cursor/live-hook-honesty-25b1
REFRESH_METHOD = MERGE_CURRENT_MAIN
MERGE_AUTHORIZATION = NOT_GRANTED
PR358_MERGED = NO
NEW_PRODUCTION_PR_CREATED = 0
```

Readiness only. `CERTIFIED != AUTHORIZED`. Cloud does not merge `#358`.

---

## Live main (reloaded 2026-08-15)

```
ACTUAL_MAIN = 4da4a4ed6028583021c22b24eb11a47a4bdf0fe0
ACTUAL_MAIN_TREE = 4dfab1548eb7fe37fef438d3a626780451a319dc
LATEST_MAIN_CI_RUN = 31874624031
LATEST_MAIN_CI_RESULT = PASS
CURRENT_MAIN_CI_REPAIRED = YES
```

`#359` post-merge verified:

```
PR359_STATE = MERGED — POST-MERGE VERIFIED
PR359_MERGE_COMMIT = 4da4a4ed6028583021c22b24eb11a47a4bdf0fe0
PR359_MERGE_TREE = 4dfab1548eb7fe37fef438d3a626780451a319dc
PARENT_1 = 689f740f6ebe1bd8c2f5be956235369c924021dc
PARENT_2 = 4ff5774a4eaba7ef943dd6088c3f03fce044e03b
POST_MERGE_MAIN_CI = PASS
```

Previous mypy stub-drift baseline is CLOSED. Do not reopen unless it regresses.

---

## D-100 / #354 reconciliation

Permanent Local-tested object (do not rewrite as a later SHA):

```
D100_TARGET_HEAD = 6041b79332c49a56894dca4d45619253e54ef51c
D100_TARGET_TREE = 78e24d48024f26c55d741f00689e788f1ec0fc01
D100_LOCAL_AUTHENTIC_IV = PASS
D098_LOCAL_REIV = PASS
ROADMAP_LOCAL_AUTHENTIC_IV = PASS
ROADMAP_SEMANTIC_CERTIFICATION = PASS
ROADMAP_AUTHENTIC_CERTIFICATION = PASS
```

Stale D-101 `PR354_SPECIAL_HOLD = YES` is replaced:

```
PR354_AUTHENTIC_HOLD = CLEARED
PR354_PRODUCT_HOLD = CLEARED
PR354_INTEGRATION_HOLD = YES
PR354_INTEGRATION_HOLD_REASON = WAITING FOR PRECEDING QUEUE + EXACT-MAIN REFRESH
PR354_STATE = AUTHENTIC CERTIFIED — INTEGRATION PENDING
PR354_MERGE_AUTHORIZATION = NOT_GRANTED
```

`#354` is not integrated. D-100 PASS does not authorize `#354`.

---

## #358 before refresh

```
PR358_HEAD_BEFORE = e44de58cb79db138c8a62427fa3febeb82502ab6
PR358_TREE_BEFORE = 3db024fafe1553bf75680a8d87b8e3d32e2fecc3
PR358_BASE_BEFORE = 9441b0c576dc54bc43a92a62a4e972889424c21f
PR358_MERGEABLE_BEFORE = CONFLICTING
OLD_PRODUCTION_TIP = ba2fc7f373ba54f31dc0b1093e11d5309153fc5e
OLD_PRODUCTION_TREE = 35d2c46b9905b4c1b671bab0f781b67ed450dccc
```

---

## Refresh

```
REFRESH_METHOD = MERGE_CURRENT_MAIN
PARENT_1 = e44de58cb79db138c8a62427fa3febeb82502ab6
PARENT_2 = 4da4a4ed6028583021c22b24eb11a47a4bdf0fe0
PR358_REFRESH_CONFLICT_COUNT = 1
PR358_PRODUCTION_SEMANTIC_CONFLICTS = 0
PR358_UNCLASSIFIED_CONFLICTS = 0
```

Conflict:

```
PATH = WORKLOG.md
CLASSIFICATION = DOCS_ADDITIVE
RESOLUTION = keep-both (D-102 header + #358 honesty + main #359/D-096 history)
```

Scope freeze unchanged: honesty hooks only. No Roadmap / Ask / Time Machine /
Context / default-project / new APIs / auth / writes / Atlas 2.3 / Memory /
Momentum / Atlas OPT.

---

## #359 preservation on composed tree

```
CONTEXT_ROUTE_PRESENT = YES
CONTEXT_NAV_PRESENT = YES
CONTEXT_MARKDOWN_RENDERER_PRESENT = YES
YAML_CLOSER_PRESENT = YES
D096_HISTORY_PRESERVED = YES
```

Compatibility closer retained:

```
closer: Any = loader.dispose
closer()
```

No version-sensitive `type: ignore` resurrected.

---

## D-100 surface vs this refresh

Compared `ProdNav.tsx` / `RoadmapPage.tsx` / `useLiveRoadmap.ts` against
exact current main `4da4a4e`:

```
D100_ROADMAP_SEMANTIC_DELTA = 0
D100_ACCEPTANCE_REUSABLE = YES
D100_RECHECK_REQUIRED = NO
```

`#358` does not carry `#354` Roadmap files. Absence vs `6041b79` is expected
and does not rewrite the D-100 object. Local PASS is reusable only because
this refresh does not change that surface relative to current main.

---

## Hygiene

```
PR_352_DISPOSITION = CLOSE WITHOUT MERGE
PR_355_DISPOSITION = SUPERSEDED BY #360 / D-096 — DO NOT MERGE
REMAINING_QUEUE = 358 → 356 → 357 → 354
```
