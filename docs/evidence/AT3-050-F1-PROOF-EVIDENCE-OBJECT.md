# AT3-050-F1 — Proof evidence must be an object

- Package: `AT3-050-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base TREE: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- MODEL CLAIM OF COMPLETION != PROOF
- LLM OUTPUT != AUTHORITY
- UNKNOWN stays UNKNOWN

## Finding

On live main, `evaluate_proof` in `src/project_atlas/atlas3/proof.py` did
`supplied = evidence or {}` then `supplied.get(name)`. When `evidence` is a
JSON string (CLI `atlas proof --evidence '"x"'`), this raises a raw
`AttributeError` instead of `Atlas3Error`. `null`/`[]` degrade more safely
(`None` becomes `{}`; a list has no `.get` and would also leak
`AttributeError`).

Classification: fail-closed input boundary. Not a Truth Core write. Not merge
authority.

## Reproduction (live main before this package)

```python
evaluate_proof(vault, "AT3-050-STR", project_id="harbor-api", evidence="x")
# AttributeError: 'str' object has no attribute 'get'
```

CLI `json.loads` of `--evidence` already succeeds for `'"x"'` and passes the
string through. The outer Atlas 3 CLI dispatcher already maps
`JSONDecodeError` to a structured `ATLAS3_ERROR` envelope, so malformed JSON
does not leak. The library must still refuse a decoded non-object.

## Remediation

If `evidence` is not `None` and not a `dict`, raise
`Atlas3Error("PROOF_EVIDENCE_INVALID", "evidence must be an object")`.
`None` remains `{}` and yields an UNKNOWN chain. A string, list, or bool is
not treated as evidence.

CLI `json.loads` of `--evidence` is unchanged. It already loads then passes
through; `JSONDecodeError` is already contained by the existing dispatcher.

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- `chatgpt_bridge.py`
- mapping CLI `JSONDecodeError` to `Atlas3Error` (does not leak today)
- merge authorization

## Validation

See WORKLOG `AT3-050-F1` for the commands actually run on the candidate object.
