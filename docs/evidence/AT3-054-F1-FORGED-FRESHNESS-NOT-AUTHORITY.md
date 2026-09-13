# AT3-054-F1 — Forged consume-path freshness is not authority

- Package: `AT3-054-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base TREE: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER != TRUTH CORE
- STALE != CURRENT
- UNKNOWN stays UNKNOWN

## Finding

On live main, Atlas 3 consume paths trusted the `freshness` field on memory
items. A caller or on-disk `reconcile.json` could stamp `freshness: CURRENT`
and the item was ranked into `current_reconciled_memory` with
`stale_presented_as_current = False`.

Coder Alpha already recomputes forged freshness
(`test_case_i_forged_freshness_field_is_not_authority`). Atlas 3 AT3-054/055
did not.

## Reproduction (live main before this package)

```python
item = {
    "text": "production is PostgreSQL 16",
    "item_type": "claim_candidate",
    "project_id": "harbor-api",
    "freshness": "CURRENT",
    "provider": "chatgpt",
    "authority": "NON_CANONICAL",
}
report = compile_memory_context(
    [item],
    project_id="harbor-api",
    project_evidence=["harbor-api production is PostgreSQL 15"],
    freshness_requirement="CURRENT",
)
# current_count == 1; stale_presented_as_current is False
```

Classification on discovery: honesty / consume-path integrity. Not a Truth Core
write. Not a cross-project leak. Not merge authority.

## Remediation

`compile_memory_context` recomputes freshness with AT3-044
`classify_freshness` before ranking. A claimed `CURRENT` that does not
recompute to `CURRENT` is downgraded. Conservative claimed `STALE` /
`UNKNOWN` are left in place. `serve_ranked_context` inherits the same
recompute.

Honesty fields:

- `caller_freshness_is_not_authority: True`
- `unproven_current_freshness_downgraded: <count>`
- per-item `claimed_freshness` and `caller_freshness_is_authority: False`

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- `chatgpt_bridge.py`
- write-path `run_memory_vertical` (already runs `reconcile_memories` /
  `apply_freshness` before ranking)
- live provider serve (EXTERNAL_BLOCKED)
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
