# AS-STUDIO-A2-003 — Task Context + Continuation (first work package)

```text
PACKAGE_ID          = AS-STUDIO-A2-003
TITLE               = Task Context + Continuation for one lane (read-only)
BASE                = #785 A2-002 mission-journey @ cd4523fc (unmerged dependency)
SURFACE             = CLI + JSON schema + Python API. NOT a Studio UI integration.
MUTATION_SURFACE    = NONE
FORMAL_IV           = NOT_STARTED
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Selected user journey

> select lane → inspect state/dependencies → retrieve relevant knowledge →
> understand supported next steps → produce continuation context

## Acceptance criteria

1. `ATLAS_STUDIO_TASK_CONTEXT_V1` validates for every path, including the
   all-inputs-missing packet.
2. Lane state comes from `atlas_dag.frontier_matrix` + `atlas_dag.stack` and is
   never re-derived; `implementation_vs_main.merged` stays `UNKNOWN`.
3. Freshness states *why*: mission-control state plus frontier-fingerprint
   divergence, which downgrades `LIVE` to `STALE`.
4. Knowledge reports `KNOWN` / `UNKNOWN` / `STALE` / `CONFLICT` / `UNAVAILABLE`
   per lens and overall, read from the real Coder Alpha lenses.
5. Exactly one supported next step, with prerequisites, offering only a
   **preview** command; `authorization = NOT_GRANTED_BY_THIS_PACKET`.
6. Recovery guidance for stale, ambiguous, unknown, conflicting and
   **uncertain-mutation** conditions; never auto-retry.
7. Continuation points at existing handoff machinery (`built_here = false`) and
   carries fingerprints plus a resume checklist.
8. Every absent input is listed in `missing`, never defaulted.
9. Read paths do not modify the vault.
10. A1 Mission Control gains no import of this module.

## Demonstration (2026-09-09, recorded)

Run through the real entry point `scripts/atlas-studio.py task-context`.

| Case | Inputs | Observed |
|---|---|---|
| **Live, real lane** | `--lane pr/786 --agent ubuntu-main --repo B0LK13/project-atlas` | `freshness=LIVE`; `lane=KNOWN head=924a4f889e83`; `ownership=UNOWNED`; `ci=PENDING`→`PASS` across runs; `vs_main=OPEN_LANE_STACKED_DEPTH_22_NOT_ON_MAIN`; 7 real blockers incl. `LANE_UNOWNED_WRITE_REQUIRES_CLAIM`, `PR_NOT_MERGED` |
| **Missing vault** | live, no `--vault` | `knowledge=UNAVAILABLE`, `missing=NO_VAULT_BOUND`, recovery names the fix |
| **Knowledge bound** | live + real vault built by `atlas init` (30 files) | `knowledge=KNOWN`, per-lens `state=UNKNOWN decisions=KNOWN unknown=KNOWN`, `missing=-` |
| **Real conflict** | vault with `review/conflicts/<p>.json` pending entry | `knowledge=CONFLICT`, `unresolved_conflicts=1` on two lenses, `KNOWLEDGE_CONFLICT` recovery |
| **Stale + mismatched** | offline fixtures: stale MC, diverged frontier fingerprint, lane owned by another agent, broken stack depth | `freshness=STALE` with both reasons; `owner=windows-main`; `vs_main=STACK_CHAIN_BROKEN_DEPTH_UNKNOWN`; `next_step=NO_SUPPORTED_ACTION` |
| **Unavailable coordination** | mission control only | `lane=UNKNOWN`, `missing=NO_FRONTIER_MATRIX,NO_STACKS` |
| **Continuation across processes** | packet written by the live run, read by a separate process with no Atlas imports | resumed identity, compared recorded head against the live head, reached `RESUME_DECISION: proceed to preview only` |

**Scope of the read-only evidence.** The vault SHA-256 tree hash is identical
before and after each run, over a real `atlas init` vault plus seeded decision
and conflict records, for the paths exercised above. It demonstrates those
paths do not write; it is **not** a proof that every possible execution path is
mutation-free.

**Surface honesty.** This package is CLI, schema and Python API only. It is
**not** wired into any Studio UI. #781 owns the native shell; the JSON packet is
the documented seam and no edit to #781 was made.

## Baseline defects found by the live path and repaired here

Both reproduced on the base commit `cd4523fc` through the **pre-existing**
`_live_claim_context`, using identical commands and environment, so they are
baseline defects rather than regressions of this package:

1. `clock=None` reached `build_studio_snapshot`, which calls `clock()`
   unconditionally → `TypeError: 'NoneType' object is not callable`.
2. `build_frontier_matrix` was called with `agent_id` and `registry`
   positionally, but everything after `snapshot` is keyword-only → `TypeError`.

Together these meant **every live Studio claim command failed before reaching
the control plane**. Repaired once in the shared `_live_frontier` helper, which
all live callers now route through, and covered by
`test_live_frontier_never_passes_none_clock_to_builders`.

A third defect was in this package's own code: the classifier read top-level
lens fields, but the real lenses nest counters under `signals`, so real
conflicts were reported as `KNOWN`. Injected-shape unit tests hid it; running
the real lenses over a real vault exposed it. Fixed by `_signal()` and covered
by `test_real_lens_nested_signals_are_classified_not_ignored`.
