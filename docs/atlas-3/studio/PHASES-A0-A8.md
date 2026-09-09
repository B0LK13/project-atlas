# Atlas Studio — phases A0–A8

Source: [#746](https://github.com/B0LK13/project-atlas/issues/746).
All checkboxes below are **future acceptance**, not existing implementation.

| Phase | Deliverable | Required exit evidence |
|---|---|---|
| A0 | Repository reuse map; daemon/Studio ADR; API/events, permissions and plugin contracts; Linux shell spike | **TECHNICALLY_COMPLETE** in PR #763 (exact-head CI); see `a0/A0-CLOSURE.md`. Owner decisions O1–O5 remain explicit. Not merged. |
| A1 | Read-only Mission Control projection over F15 panels (+ freshness/attention) | **TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED** — see `a1/A1-CLOSURE.md` + `a1/A1-EVIDENCE.md`. Semantic attack suite 10/10; O1/O6 APPROVED; `MISSION_CONTROL_HUMAN_COHERENCE=PROVEN`; no mutation; Tauri deferred. Not merged. `CI_PASS != FORMAL_IV`. |
| A2 | Governed claim/dispatch/handoff/open-worktree/terminal | **A2-001 OWNERSHIP_CLAIM IMPLEMENTED_IN_LANE** — see `a2/A2-EVIDENCE.md` + ADR-035. Dispatch/steal-auto/handoff-delivery/worktree/PTY = NOT_STARTED. Exit evidence for A2-001: denial/authz/freshness/idempotency tests; control-plane execute/refuse via F04 emitter; audit/receipt. FORMAL_IV / merge = NOT_STARTED. |
| A3 | Runtime and provider/harness integration | Model neutrality across ≥2 adapters; secrets isolation; sandbox/cost enforcement; durable tasks across UI failure |
| A4 | Code/diff/test/terminal/PR lifecycle | End-to-end isolated feature with exact-object CI/IV, authorized merge, postmerge and seal; external IDE handoff |
| A5 | Chronicle and Knowledge Plane UX | Capture→quarantine/normalization→validation→projection; provenance, redaction, dedup, human-region preservation |
| A6 | Research/design workflow | Sourced claims, uncertainty, architecture comparison, ADR and executable DAG lineage |
| A7 | Evals/traces/experiments/improvement | Baselines, isolated holdouts, regression/security gates, shadow/canary/rollback; no automatic Atlas-OPT unlock |
| A8 | Autonomous workstation | Routine complete lifecycle under policy; proven recovery and denied unsafe actions |

## Dependency law

```text
A0 → A1 → A2 → A3 → A4
A5 builds on existing knowledge foundations + A0/A1 contracts
A6 requires context/knowledge lineage
A7 requires reliable traces/evals
A8 requires all applicable preceding gates
```

Do not postpone existing knowledge features until a rebuild of A5.

## Coordination reuse (mandatory)

A1 Mission Control and later mutation surfaces **must** consume the Features 1–16
coordination control plane (`scripts/atlas_dag/` and related schemas) as the
authoritative DAG/frontier/ownership/CI-IV/seal/residual/telemetry projection
source. Recreating parallel eligibility or ownership logic in Studio is forbidden.
