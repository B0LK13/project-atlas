# Hidden holdouts — scoring capability required

Live hidden holdout set: `EV-HOLD-101`, `EV-HOLD-102` (fresh ids). The earlier
`EV-HOLD-001` / `EV-HOLD-002` cases were **retired** (D-ULTRA-RESUME-010 §8)
because their answers leaked into git history; they now live as PUBLIC
regression cases under `fixtures/eval/regression/` and are no longer hidden.

These cases are **not** part of training or autolab path manifests.
`project_atlas.eval_substrate` fails closed if training/autolab roles resolve
any path under this directory.

Holdout case JSON in git carries **no plaintext `expected` field**. Expected
answers live in a private map outside git (`fixtures/eval/holdouts/private/`,
gitignored) and are loaded only when both of the following are set:

- `ATLAS_EVAL_SCORING_CAPABILITY=1`
- `ATLAS_EVAL_HOLDOUT_EXPECTED_PATH=<absolute path to private map>`

Calling `load_cases(..., "scoring")` without the capability gate returns the
public-only view — **role strings are not a trust boundary**.

Generated score receipts drop per-row holdout answer signal — `predicted_norm`,
`matched`, and `expected_norm` are omitted (each reconstructs the private answer
key), leaving only a `expected_redacted` marker plus summary-level aggregate
counts. Durable artifacts must not persist or reconstruct secret answers.

The in-process capability gate above is **advisory** (a same-process adversary
can set the env var). The true trust boundary is the out-of-process scoring
broker (`project_atlas.scoring_broker`, `AS-2.2-EVAL-BROKER-001`): the optimizer
holds only a session handle, submits candidate predictions keyed by opaque case
ids, and receives ONLY a bounded result (aggregate metrics, hard gates, opaque
ids, receipt digest, attempts remaining). The broker process alone holds the
private expected answers and enforces a submission budget against bound-oracle
extraction.
