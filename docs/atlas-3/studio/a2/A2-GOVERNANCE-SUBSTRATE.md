# A2 governance substrate — reusable control loop

```text
AS_STUDIO_A2_GOVERNANCE_SUBSTRATE = IMPLEMENTED_IN_LANE
FIRST_INSTANCE = OWNERSHIP_CLAIM
FUTURE_ACTIONS = DECLARED_NOT_STARTED (attach via registry)
STUDIO_UI != AUTHORITY
INTERFACE != SOURCE_OF_AUTHORITY
```

## Purpose

A2 establishes one reusable governance loop for every future Studio action.
OWNERSHIP_CLAIM is the first **instance**, not a one-off mutation shortcut.

```text
MISSION CONTROL TRUTH
  → CANDIDATE (projection / ranking — non-authoritative)
  → PREVIEW (dry advice — PREVIEW != EXECUTION)
  → INTENT (typed request — REQUESTED != EXECUTED)
  → POLICY + AUTHORITY + FRESHNESS EVALUATION
  → CONTROL PLANE REVALIDATION
  → EXECUTE | REFUSE
  → EVIDENCE (decision packet)
```

## Module

| Piece | Role |
|---|---|
| `scripts/atlas_studio/governance.py` | Registry, shared honesty, authz-field reject, evaluate/execute entry |
| `scripts/atlas_studio/action_intent.py` | OWNERSHIP_CLAIM handler + claim-* preview/intent helpers |
| Schemas | `ATLAS_STUDIO_ACTION_{INTENT,PREVIEW,DECISION}_V1` |

## Separation (must stay true)

| Concern | Owner | Studio may |
|---|---|---|
| Intent | Typed request object | Mint request; never mint grants |
| Authority | Control plane / daemon / emitter policy | Surface capability claims as informational only |
| Freshness | Intent `max_age` + MC/frontier fingerprints + expect_head | Bind fingerprints; never treat stale as current |
| Policy | Emitter permission + ownership mutex + agent registry | Preview expected policy; never self-pass |
| Execution | Registered handler.apply_authorized after EXECUTE_ALLOWED | Invoke only via substrate; dry_run never mutates |
| Evidence | Decision packet with reasons + honesty | Project decisions; never invent authority from UI |

## Outcome labels (review-closure hardening, PR #776)

| Path | `decision` | `dry_run` | `mutated` | Notes |
|---|---|---|---|---|
| Evaluate refused | `REFUSED_*` | false | false | reasons carry the refusal code |
| Evaluate allowed (no execute) | `EXECUTE_ALLOWED` | false | false | evaluate-only |
| Dry-run execute | `EXECUTE_ALLOWED` | **true** | false | reason `DRY_RUN_NO_EMIT`; **DRY_RUN != EXECUTED** — the label never says something ran |
| Wet execute, confirmed | `EXECUTED` | false | **true** | only path to `EXECUTED` with `mutated=true` |
| Wet execute, idempotent duplicate | `REFUSED_IDEMPOTENT_ALREADY_CLAIMED` | false | false | bus already holds the event |
| Executor raised / returned no packet | `EXECUTION_FAILED` | false | false | `evidence.mutation_state = UNKNOWN`; never reported as success, never a bare exception |

`mutated=true` means the executor **confirmed** a control-plane mutation.
`mutated=false` with `EXECUTION_FAILED` does not mean "nothing happened" — it
means nothing was confirmed; the evidence says `UNKNOWN`.

Repository identity: `apply_authorized` for OWNERSHIP_CLAIM refuses with
`REFUSED_POLICY / EXPECTED_REPO_REQUIRED_AT_EXECUTE` unless an explicit
`expected_repo` is supplied; the CLI makes `--repo` **required** on
`claim-execute`. `gh` auto-resolution of "the current repo" is not authority.

## Registry contract

```python
from atlas_studio import governance as gov
import atlas_studio.action_intent  # registers OWNERSHIP_CLAIM

gov.supported_actions()
# OWNERSHIP_CLAIM = IMPLEMENTED
# CI_DISPATCH / IV_REQUEST / HANDOFF_DELIVER / STEAL_EXECUTE /
# MERGE / WORKTREE_OPEN = NOT_STARTED
```

Unknown or NOT_STARTED action types refuse with `REFUSED_UNSUPPORTED_ACTION`.

Registration is fail-closed: `register_action` refuses to replace an existing
`IMPLEMENTED` handler (`GovernanceError(DUPLICATE_REGISTRATION:<type>)`).
There is **no** `replace=True` escape hatch in this package. Re-registering
the same handler object is idempotent; a `NOT_STARTED` attach point may be
promoted to `IMPLEMENTED`; `declare_not_started` never demotes an
`IMPLEMENTED` entry.

Ordinary executor exceptions become `EXECUTION_FAILED` with redacted
exception type evidence (`mutation_state=UNKNOWN`). `KeyboardInterrupt` and
`SystemExit` are not caught. If evidence construction itself fails after an
executor exception, the substrate raises
`GovernanceError(EVIDENCE_PERSISTENCE_FAILED_AFTER_EXECUTOR:...)` — it does
not claim success or claim that evidence was persisted.

Whitespace-only or empty `expected_repo` is treated as missing and refused
with `EXPECTED_REPO_REQUIRED_AT_EXECUTE` before live resolution.

Handlers must:

1. `evaluate` — never mutate; return `EXECUTE_ALLOWED` or `REFUSED_*`
2. `apply_authorized` — only after substrate confirms ALLOWED; revalidate at boundary

## Attach path for next actions

1. Implement handler (`evaluate` + `apply_authorized` reusing `atlas_dag` builders).
2. `gov.register_action(handler, notes=...)`.
3. Widen intent schema `action_type` enum when IMPLEMENTED.
4. Add refusal/attack tests; keep A1 Mission Control free of mutation imports.

## Honesty stamps

```text
STUDIO_UI != AUTHORITY
ATTENTION != AUTHORIZATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
STALE != CURRENT
UNKNOWN != HEALTHY
BUTTON != MUTATION
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED
IMPLEMENTED != MERGED
```
