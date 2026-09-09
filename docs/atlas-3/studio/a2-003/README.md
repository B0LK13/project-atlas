# AS-STUDIO-A2-003 — Task Context + Continuation (read-only, one lane)

```text
PACKAGE_ID            = AS-STUDIO-A2-003
BASE                  = #785 A2-002 mission-journey tip (explicit, unmerged dependency)
                        ← #776 A2-001 tip 2debb778 ← #770 A1 ← #763 A0 ← coordination stack
MUTATION_SURFACE      = NONE
NEW_STORES            = NONE (composes existing builders and lenses)
FORMAL_IV             = NOT_STARTED
MERGE_AUTHORIZATION   = NOT_GRANTED
TASK_CONTEXT          != AUTHORITY
```

## The user journey this closes

> For a selected lane the user sees its current state and why the evidence is
> fresh or stale, its dependencies and specific blockers, the candidate identity
> and whether it is on main, what the compiled knowledge says is known / unknown /
> stale / conflicting, the one supported next step and its prerequisites, and a
> continuation the next session can resume from — with every missing input named.

`atlas-studio mission-journey` (#785) answers "what is the mission and what
knowledge is around it". `atlas-studio task-context` answers "what do I need to
know to act on **this lane** right now, and how does another session pick it up".

## Contract

Schema `ATLAS_STUDIO_TASK_CONTEXT_V1` (`schemas/atlas_studio_task_context_v1.schema.json`).

| Section | Source (reused, never re-derived) | States |
|---|---|---|
| `lane_state` | `atlas_dag.frontier_matrix` rows for the lane + `atlas_dag.stack` record | `KNOWN` / `UNKNOWN`; `implementation_vs_main.merged` is always `UNKNOWN` (not derivable from the frontier) |
| `freshness` | A1 Mission Control freshness + frontier fingerprint comparison | `LIVE` / `STALE` / `OFFLINE` / `UNKNOWN` with `reasons[]` |
| `attention` | A1 attention items referencing this lane | `attention_ne_authorization` on every item |
| `knowledge` | `project_atlas.project_{state,decisions,unknown}.build_*_lens` | `KNOWN` / `UNKNOWN` / `STALE` / `CONFLICT` / `UNAVAILABLE` per lens and overall (conflict dominates) |
| `next_step` | best RUNNABLE + agent-eligible frontier action | `SUPPORTED` / `NO_SUPPORTED_ACTION`; `authorization = NOT_GRANTED_BY_THIS_PACKET`; only a **preview** command is offered |
| `recovery` | rules over the above | condition → guidance; includes `UNCERTAIN_MUTATION`: never auto-retry |
| `continuation` | pointers to `atlas-dag handoff --mode resume` and `atlas handoff create`; optional `export_agent_context` (no refresh) | `built_here = false` always |
| `missing` | every absent input | explicit list, never defaulted |

## Continuation verification (export → import → verdict)

`--verify-continuation PACKET` re-reads truth and compares it with a recorded
packet, so a resuming session does not have to hand-roll the check:

```bash
atlas-studio task-context --lane pr/786 --agent A --repo O/N --json > ctx.json   # export
atlas-studio task-context --verify-continuation ctx.json --agent A --repo O/N    # import + verify
```

**Identity decides the verdict; snapshot drift is advisory.** Lane, repository,
head, ownership and owner changes mean the recorded evidence no longer describes
the world. Fingerprints and CI status move on every rebuild as the estate
advances, so they are reported as `advisory_changes` with guidance to re-mint
intents (a stale fingerprint is refused as `REFUSED_STALE` at claim time) — this
was found live, where two consecutive exports of an unchanged lane already
differed in both fingerprints.

Verdict `ATLAS_STUDIO_CONTINUATION_VERDICT_V1`: `STILL_VALID` (exit 0),
`INVALIDATED` (exit 1, with the changed fields listed), or `UNVERIFIABLE`
(exit 1) when the packet is unreadable, schema-invalid, or the lane could not
be resolved on either side. A field that is absent on one side is reported as a
change, never silently treated as equal. `IMPORTED_CONTEXT != PERMISSION`: a
`STILL_VALID` verdict says the recorded evidence still describes the world, and
authorizes nothing.

## Requirements served (#746 register)

06 Mission Control · 13 DAG/work graph · 18 CI/IV (identity fields surfaced, never
asserted) · 20 Knowledge · 21 Decisions · 29 Offline/reconnect · 35 Bounded
context · 39 Evidence-backed retrieval · 44 Audit (continuation fingerprints) ·
50 Replay (inspection without side effects).

## Integration seam for #781 (native shell)

The packet is JSON; the TUI formatter is optional. A native view renders
`lane_state`, `knowledge.lenses`, `next_step` and `recovery` directly and must
keep `honesty` and `missing` visible. No edit to #781 is required or made.

## Non-goals

No CI_DISPATCH / IV_REQUEST / HANDOFF_DELIVER / STEAL_EXECUTE / MERGE /
WORKTREE_OPEN. No new knowledge store, ledger, or eligibility engine. No change
to A2-001 intent handling (#782 binds `target_repo`; this package does not
touch intents).
