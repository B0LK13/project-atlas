# Atlas 3.0 — Product experience

UX follows canonical data contracts. UI must not invent a second model.

## Atlas Pulse — `atlas pulse`

Project-scoped, evidence-backed, temporal, deterministic, honest about
UNKNOWN, non-authoritative where derived.

Must answer:

| Question | Source (reuse first) |
|---|---|
| What changed? | `project_changed` + ledger |
| What matters? | attention / next / brief |
| What became stale? | inventory drift + memory freshness + kdiff |
| What conflicts? | Core conflicts + memory conflicts |
| What failed? | ledger failures + handoff/proof failures |
| What was decided? | decisions lens + confirmed owner items only |
| What requires attention? | failures + conflicts + attention lens; not a change fallback |
| What should I look at next? | next lens; stale/unverified stay honest |

Pulse is a **derived lens**. It is not Truth Core.

## Atlas Start — `atlas start`

Compile a bounded context briefing. No arbitrary RAG dump.
**Token/context budget is required.**
**Freshness requirement is required** (`CURRENT` | `ALLOW_STALE_HISTORICAL` |
`UNKNOWN`). `CURRENT` refuses stale evidence as current verified truth.

Required sections:

1. Project identity
2. Current verified truth
3. Recent material changes
4. Relevant decisions
5. Open conflicts
6. Open unknowns
7. Stale context
8. Current task
9. Owner constraints
10. Recent failures
11. Next relevant actions

Missing evidence stays UNKNOWN. Start must not invent a current task.

## Agent proof — `atlas proof <task-id>`

```text
TASK → IMPLEMENTATION → TESTS → CI → INDEPENDENT VERIFICATION
     → ADV → INTEGRATION → POST-MERGE
```

`MODEL CLAIM OF COMPLETION != PROOF`.

## Future UX surfaces (contracts first)

| Surface | Backed by | Not allowed to |
|---|---|---|
| Atlas Home | Pulse + Start + twin health | Invent authority |
| Atlas Pulse | AT3-015 | Hide UNKNOWN |
| Timeline | ledger + bitemporal | Use wall-clock as valid-time |
| Truth Graph | claims + twin relationships | Graph winners |
| Time Machine | existing kdiff | Second clock |
| Decision Explorer | decisions + owner_origin | Infer owner decisions from model paraphrase |
| Impact Explorer | impact_graph + twin | Trust scores |
| Mission Command Center | orch DAG / leases (read) | Self-merge |

## CLI targets (additive)

```text
atlas pulse  --vault <dir> --project <id> [--json]
atlas start  --vault <dir> --project <id> --budget <n> [--freshness CURRENT] [--json]
atlas proof  <task-id> --vault <dir> [--json]
atlas memory sync|status|search|conflicts|stale|providers
atlas capabilities
atlas compat --vault <dir>
```

`atlas memory sync` is a status/capability command in this slice, not a live
full-account sync. ChatGPT live history remains **not generalized**.
