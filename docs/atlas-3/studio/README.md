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
FORMAL_IV = NOT_STARTED
```

## Next

1. Owner merge/IV decisions for A0/A1/A2-001 remain separate from technical completeness.
2. Later A2.x: dispatch / steal-auto / handoff delivery / worktree behind the same intent bridge.
3. Formal IV / verifier bind remains `EXTERNAL_IV_GATED` / NOT_STARTED for A2.

## A0 package

See [`a0/`](./a0/) and [ADR-034](../../adr/ADR-034-studio-daemon-authority.md).
