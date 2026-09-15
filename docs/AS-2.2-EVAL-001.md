# AS-2.2-EVAL-001 — Eval substrate (hidden holdouts)

Status: **P0 substrate**. Not ATLAS-OPT. Not RL/Prime. Not PREP deepen churn.
Not authentic PILOT.

## Purpose

Ship a tip-safe evaluation substrate with:

1. **Public fixtures** for training / autolab config paths.
2. **Hidden holdouts** isolated so those paths cannot resolve or load them.
3. **Scoring capability gate** — `role="scoring"` alone is not authorization;
   holdout access requires `ATLAS_EVAL_SCORING_CAPABILITY=1` plus a private
   expected map path (`ATLAS_EVAL_HOLDOUT_EXPECTED_PATH`).
4. **No plaintext expected in git-tracked holdout bodies** or durable receipts.
   Durable receipts drop per-row holdout `predicted_norm` / `matched` /
   `expected_norm` (those reconstruct the answer key); holdout outcome survives
   only as summary aggregate counts.
5. **Deterministic scoring hooks** (exact / prefix; objective counts only).

> **Advisory gate, not a trust boundary.** `ATLAS_EVAL_SCORING_CAPABILITY=1` is a
> process-local env var and is self-elevatable by a same-process adversary. It
> prevents accidental holdout exposure but is not an authorization boundary. A
> true out-of-process capability broker is a tracked follow-up (out of scope
> here).

## Layout

```
fixtures/eval/
  public/cases/          # readable by training + autolab + scoring
  holdouts/hidden/cases/ # scoring only
  configs/
    training.paths.json  # public roots only
    autolab.paths.json   # public roots only
    scoring.paths.json   # public + holdouts
```

Module: `project_atlas.eval_substrate`

## Gates (fail closed)

| Attempt | Result |
|---|---|
| training/autolab resolve holdout path | `holdout-isolated:*` |
| scoring holdout access without capability | `holdout-capability-required` |
| holdout plaintext in git case body | `holdout-plaintext-forbidden:*` |
| holdout answer signal in durable receipt | per-row `predicted_norm`/`matched`/`expected_norm` dropped; only `expected_redacted` marker + summary aggregates kept |
| wake ATLAS-OPT-001/002 flags | `opt-gated:*` |
| RL / Prime / invent-pilot / subjective score | `forbidden-claim:*` |
| authority promote | `forbidden-claim:promote_authority` |

## OPT

`ATLAS-OPT-001` / `ATLAS-OPT-002` remain **gated**. This package does not import,
enable, or wake OPT. Vertical PASS later may unlock OPT — not here.

## Truth boundary

`EVAL SUBSTRATE ≠ OPT / ≠ RL / ≠ PRIME / ≠ AUTHORITY / ≠ SUBJECTIVE SCORE`

## Related (non-substitutes)

- `AS-2.0-AGENT-EVAL-001` — agent shadow receipts (no holdout isolation).
- `docs/atlas-2.2/benchmarks/` — Hybrid Retrieval 2 PREP sketches (not this substrate).
