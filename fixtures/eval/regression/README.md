# Retired holdout regression cases (D-ULTRA-RESUME-010 §8)

These cases were **formerly hidden holdouts** (`EV-HOLD-001`, `EV-HOLD-002`)
whose expected answers were committed to git history (commit `388b218`, later
scrubbed from the working tree in `a8e13c4` / `abd328b`). Because the answers
(`conflict-detected`, `lineage-`) remain recoverable from history, they no
longer provide hidden-evaluation value and have been **retired**.

They are kept here only as **PUBLIC regression** cases:

- `visibility: "public"` and `case_class: "regression"` — never `holdout`.
- They live **outside** `holdouts/hidden/`, so no eval role treats them as
  hidden holdouts (`project_atlas.eval_substrate` never attaches a private
  expected answer to them).
- Their `expected` answers are plaintext because those answers are already
  public in git history; committing them here reveals nothing new.
- `retired_from` records the original compromised holdout id.

The live hidden holdout set uses **fresh** case ids (`EV-HOLD-101`,
`EV-HOLD-102`) whose expected answers have **never** been committed. Those
answers are held only by the out-of-process scoring broker
(`project_atlas.scoring_broker`, `AS-2.2-EVAL-BROKER-001`) and are loaded at
runtime from an out-of-tree, gitignored location.
