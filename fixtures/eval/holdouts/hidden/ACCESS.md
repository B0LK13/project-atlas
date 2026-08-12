# Hidden holdouts — scoring capability required

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
