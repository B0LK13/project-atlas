# FULL PRODUCT DEMO SCOPE (D-177)

```
DEMO_SCOPE_FROZEN = YES (intent)
AS_OF_MAIN = a17949c6df9b4d004ffe03eb47b0934e3735204d
BANNER = TECHNICAL DEMO — NOT RELEASE CERTIFIED — NOT AUTHENTIC PILOT
OPTIONAL_SCOPE_EXPANSION = FORBIDDEN
```

Built from **live CLI / packages on post-#504 main**, not aspirational backlog.
Do not expand because another wrapper PR exists.

## Classification legend

| Class | Meaning |
| --- | --- |
| MERGED_WORKING | On main; exercised or strongly evidenced |
| MERGED_UNVERIFIED | On main; needs demo act verification |
| OPEN_CERTIFIED | Open PR tip certified pending owner (frozen until auth) |
| OPEN_RECERT_REQUIRED | Open; needs recert/IV before owner |
| UNIQUE_REQUIRED | Unlanded unique work; may be demo-critical |
| OPTIONAL_2X | Useful but not required for FULL_LIVE_DEMO_READY |
| DEFER_3X | Explicitly post-demo |
| OBSOLETE / SUPERSEDED | Do not revive |

## A–I matrix (summary)

See `full-product-demo-scope.json` for machine-readable rows.

### Demo-critical cores (must PASS for FULL_LIVE_DEMO_READY)

- Estate discover ≠ ingest
- Ingest → build-indexes → validate
- Query / Ask2 with evidence + UNKNOWN honesty
- Conflict / changed / source-health representation
- Context / handoff for agent start
- CLI surface (API/Web/MCP parity for one object)
- Owner gate non-escalation (D149-001 CLOSED on main)
- Control plane / durable host (post-#476)

### Open queue vs demo

| PR | Class | DEMO_CRITICAL |
| --- | --- | --- |
| #472 architecture LIVE_API + secret redact | OPEN_CERTIFIED | YES (API honesty) |
| #473 workflow metrics | OPEN_CERTIFIED | YES (ops truth) |
| #475 isolation ADV harness | OPEN_CERTIFIED* | YES (isolation demo) |
| #474 terminal encoding | OPEN_CERTIFIED | YES (Windows CLI demo; CORE_DIFF_IV PASS) |
| #471 context freshness | OPEN_RECERT_REQUIRED | YES (freshness honesty) |
| #499–#503 wrappers | OPTIONAL_2X / DUPLICATIVE | NO |

\* #475 needs claim-scope wording correction; production tests valid.

### MCP leftovers (inventory) — representative parity, not every wrapper

| Item | Class | Demo |
| --- | --- | --- |
| graph MCP | UNIQUE_OPTIONAL | Not demo-critical. Graph is demonstrated via CLI/API/Web. |
| mission/workspace MCP | UNIQUE_OPTIONAL | Non-demo unless an explicit mission act requires it. |
| project-attention MCP | UNIQUE_OPTIONAL | Not demo-critical. Attention is on intended non-MCP surfaces. |
| unknown/changed MCP | UNIQUE_OPTIONAL | Not demo-critical. Representative MCP parity is proven elsewhere. |

`DEMO_CRITICAL_MISSING` therefore excludes graph MCP and project-attention MCP.

## Freeze rule

New open PRs do **not** enter this scope unless they close a DEMO_CRITICAL_MISSING row.
