# AS-OPT-GATE-001 — Governed experiment and promotion boundary

Status: **P0 trust boundary**. Not Atlas-OPT. Not AutoLab. Not RL/Prime.
Does not set `ATLAS_OPT_WAKE_GATE` to anything other than `CLOSED`.

## Purpose

Ship the governed experiment / promotion contract required before Atlas-OPT
may become eligible to wake:

1. Typed, non-overridable **hard gates** that precede quality score.
2. **Sealed experiment envelope** so candidate inputs cannot mutate the
   evaluator, policies, thresholds, or baseline after start.
3. Privacy-safe, reconstructable **experiment receipt**.
4. Explicit promotion engine: `PROMOTE_ELIGIBLE` | `REJECT` |
   `INVALID_EXPERIMENT`.

`PROMOTE_ELIGIBLE` is not MERGED, not DEPLOYED, and not AUTHORITATIVE.
This package never launches AutoLab, never mutates retrieval/prompts/models,
and never merges or deploys a candidate.

## Reuse (no parallel scorer)

| Concern | Existing authority |
|---|---|
| Public / regression scoring | `project_atlas.eval_substrate.score_cases` |
| Hidden holdout aggregates | out-of-process `ScoringBrokerSession.submit` |
| Holdout isolation | `AS-2.2-EVAL-001` + `AS-2.2-EVAL-BROKER-001` |
| Secret scanning | `project_atlas.secrets.scan_text` (metadata only) |

Caller-supplied quality scores and gate outcomes are ignored.

## Hard gates

Each of the following is `PASS` or `FAIL`. A missing or unknown gate is
fail-closed. `UNKNOWN` is never emitted and cannot count as `PASS`.

- `security`
- `provenance_integrity`
- `authority_integrity`
- `unknown_honesty`
- `conflict_honesty`
- `evidence_integrity`
- `determinism`
- `project_isolation`
- `holdout_isolation`

Invariant: **any hard-gate FAIL → `PROMOTION = REJECT`**, even if the
engine-computed quality score is perfect. Quality is not considered for
promotion until every required gate is `PASS`.

## Sealed envelope

At experiment start the engine digests:

- evaluator implementation (`eval_substrate`, scoring broker, this module, schemas)
- public + regression evaluation dataset
- holdout broker contract + hidden holdout *metadata* (never expected answers)
- scoring policy, hard-gate policy, thresholds, honesty catalog
- experiment receipt schema
- baseline configuration

Candidate configuration may contain only `candidate_id`, optional `label` /
`seed`, and allowlisted `parameters`. If any sealed file or policy snapshot
changes before promotion, the experiment is `INVALID_EXPERIMENT`.

Private holdout expected answers are **not** read by this module and are
**not** included in any digest, receipt, log, or exception.

## Promotion

All of the following are required for `PROMOTE_ELIGIBLE`:

1. experiment valid (seal intact, broker scored, policies safe)
2. every hard gate `PASS`
3. public quality improvement meets sealed thresholds
4. hidden holdout aggregate does not regress
5–9. security / provenance / authority / UNKNOWN honesty / conflict honesty
   regressions = 0 (implied by those gates passing)
10. reproducibility receipt schema-valid and internally consistent

Otherwise `REJECT` or `INVALID_EXPERIMENT`. Fail-closed cases include missing
evaluator digest, missing/unknown gate, invalid receipt, schema mismatch,
malformed candidate config, unavailable or partial scoring broker, missing
threshold, and sealed-component drift.

## Receipt

Durable JSON under `generated/ops/opt-gate/` (optional vault write). Semantic
content is deterministic: no wall-clock, `generated.by` only, `sort_keys=True`.
Holdout section is bounded aggregates only — no expected answers, no per-row
match flags, no private case bodies.

## OPT

`ATLAS_OPT_WAKE_GATE` remains **CLOSED**. Vertical evaluator stability is
decided by a separate independent agent after merge — this package does not
declare `EVALUATOR_STABLE`.
