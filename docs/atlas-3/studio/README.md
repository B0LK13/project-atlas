# Atlas Studio — program package

| Field | Value |
|---|---|
| Master epic | [#746](https://github.com/B0LK13/project-atlas/issues/746) |
| Intake ID | `AS-STUDIO-INTAKE-20260908-01` |
| Status | **CANONICAL PRODUCT PACKAGE (docs)** — implementation starts at A0 |
| Precedence | Owner directives > landed `main` truth > this package > historical roadmaps |
| Honesty | `PREP != IMPLEMENTED` · `STUDIO_UI != AUTHORITY` · `CI_PASS != FORMAL_IV` |

Atlas Studio is the Linux-first **human operating surface** for the Engineering,
Knowledge, and Improvement Planes. It is a projection and control interface over
Atlas truth — never a second truth authority.

This directory is the **canonical documentation package** synchronized from the
GitHub master epic. It does **not** claim a delivered workstation, unlocked
Atlas-OPT, waived verification, or merge/deploy authority.

## Design laws (binding)

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
MODEL_PROVIDER != ATLAS_ARCHITECTURE
STUDIO_CRASH != AGENT_TASK_TERMINATION
```

## Documents in this package

| Document | Role |
|---|---|
| [INTAKE-AS-STUDIO-INTAKE-20260908-01.md](INTAKE-AS-STUDIO-INTAKE-20260908-01.md) | Durable intake record + pipeline status |
| [REQUIREMENTS-REGISTER.md](REQUIREMENTS-REGISTER.md) | 60-section requirements register (from #746) |
| [PHASES-A0-A8.md](PHASES-A0-A8.md) | Delivery gates and exit evidence |
| [A0-BRIEF.md](A0-BRIEF.md) | First executable package `AS-STUDIO-A0-001` brief |
| [RELATION-TO-CODER-ALPHA-AND-ATLAS-3.md](RELATION-TO-CODER-ALPHA-AND-ATLAS-3.md) | Reconciliation with existing north stars |

## Coordination control plane (implementation-layer foundation)

The autonomous coordination stack (Features 1–16 under `scripts/atlas_dag/`) is
**implementation-complete** on the stacked PR tip and exact-head CI validated.
Studio A0+ **must consume** those primitives (snapshot, router, stacks, events,
verifiers, dispatch, evidence, handoffs, seal, frontier, steal, residuals,
telemetry, control-view, e2e-harden) rather than recreate them.

Honesty stamps that remain true until owner authority changes them:

```text
ATLAS_AUTONOMOUS_COORDINATION_STACK = FULLY_INTEGRATED_AT_IMPLEMENTATION_LAYER
IMPLEMENTED != MERGED_TO_MAIN
CI_PASS != FORMAL_IV
EXTERNAL_IV_GATED != VERIFIED
```

## What this package is not

- Not a Tauri/desktop implementation.
- Not Knowledge Plane or Improvement Plane runtime delivery.
- Not merge authorization.
- Not independent verification of #746 research leads / numerical examples.

## A0 package (lane)

See [`a0/`](./a0/), [A0-CLOSURE.md](./a0/A0-CLOSURE.md), and
[ADR-034](../../adr/ADR-034-studio-daemon-authority.md).

```text
AS_STUDIO_A0_001 = TECHNICALLY_COMPLETE
A0_REMAINING_OWNER_DECISIONS = EXPLICIT
IMPLEMENTED != MERGED
MERGE_AUTHORIZATION = NOT_GRANTED
```

## A1 Mission Control (lane)

See [`a1/`](./a1/), [A1-CLOSURE.md](./a1/A1-CLOSURE.md), and
[A1-EVIDENCE.md](./a1/A1-EVIDENCE.md).

```text
AS_STUDIO_A1_001 = TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED
MISSION_CONTROL_HUMAN_COHERENCE = PROVEN
STUDIO_MUTATION_AUTHORITY = NONE
IMPLEMENTED != MERGED
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED
```

## A2 governed OWNERSHIP_CLAIM (lane)

See [`a2/`](./a2/) and [ADR-035](../../adr/ADR-035-studio-governed-action-intent.md).

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
DISPATCH_STEAL_AUTO = NOT_STARTED
BUTTON != MUTATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
FORMAL_IV = PASS_ON_TIP_2debb778 (see a2/A2-001-STATUS-CURRENT.md + a2/iv/)
MERGE_AUTHORIZATION = NOT_GRANTED
```

## A2-002 Mission Journey (lane)

See [`a2-002/`](./a2-002/).
| [a2-003/](a2-003/README.md) | AS-STUDIO-A2-003 Task Context + Continuation (RO, one lane; composes A1 + A2-002 + Coder Alpha lenses) |

```text
AS_STUDIO_A2_002 = IMPLEMENTED_IN_LANE (RO journey packet)
BASE = certified A2 tip 2debb778 (explicit dependency)
JOURNEY != MUTATION
KNOWLEDGE != PERMISSION
FORMAL_IV = NOT_STARTED
```

## A2-004 Action Evidence & Recovery (lane)

See [`a2-004/`](./a2-004/).

```text
AS_STUDIO_A2_004 = IMPLEMENTED_IN_LANE (RO evidence + recovery)
BASE = A2-002 tip (stack disclosed; certified A2 tip preserved)
AUTO_RETRY = FORBIDDEN
MONITOR != RE-EXECUTE
CAPTURE != AUTHORITY
FORMAL_IV = NOT_STARTED
```

## A2-005 Intent Continuity (lane)

See [`a2-005/`](./a2-005/).

```text
AS_STUDIO_A2_005 = IMPLEMENTED_IN_LANE (RO continuity after interrupt)
STACKED_WITH = A2-004 on feat/as-studio-a2-004-action-evidence (#788)
STALE_INTENT != PERMISSION
DUPLICATE_SUBMIT != AUTO_RETRY
INSPECT != EXECUTE
FORMAL_IV = PASS on subject tip 4904125f (with A2-004)
```

## A2-006 Mission Session Continuity (lane)

See [`a2-006/`](./a2-006/).

```text
AS_STUDIO_A2_006 = IMPLEMENTED_IN_LANE (coherent session + binding + resume)
BASE_FREEZE = #788 tip 10df59fb
FORMAL_IV = NOT_STARTED (does not inherit 4904125f)
TASK_CONTEXT dependency = explicit UNAVAILABLE until #786 on stack
```

## Next

1. Owner merge/IV decisions for A0/A1/A2-001 remain separate from technical completeness.
2. Human review-thread adjudication on #776 remains external.
3. Later A2.x: dispatch / steal-auto / handoff delivery / worktree behind the same intent bridge.
4. A2-002 / A2-004 / A2-005 / A2-006 successors require their own exact-head CI + formal IV where claimed.
5. Avoid overlapping #786 (task-context), #782 (target_repo), #781 (visual shell).
6. Optional Formal IV delta for #788 tip `10df59fb` (write-decision + pointers) is separate from A2-006.

## A0 package

See [`a0/`](./a0/) and [ADR-034](../../adr/ADR-034-studio-daemon-authority.md).
