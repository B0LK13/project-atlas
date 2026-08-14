# D-072 #348 merge and post-merge verification

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D049-MERGE-072`

```
MERGE_AUTHORIZATION = VALID
PR_348_MERGED = YES
POST_MERGE_VERIFICATION = PASS
D_049_STATE = POST_MERGE_VERIFIED
```

## Fail-closed pre-merge (measured immediately before merge)

```
CURRENT_MAIN = 072f1395ee310a876e93d633264f3ece43cecc3c
PR_348_HEAD = d7624753d9fa506bf3b4664ecfbad2af408d9834
PR_348_TREE = 2250a7bf1162db778b26a41d94e6e6f7d6b9480c
mergeable = MERGEABLE
mergeStateStatus = CLEAN
```

Hashes matched the owner authorization. Authorization was not reinterpreted.

## Actual merge identity (GitHub merge commit)

```
PREVIOUS_MAIN = 072f1395ee310a876e93d633264f3ece43cecc3c
MERGE_COMMIT = 198350319c17b4de0665f972fda0bc51420cd686
MERGE_TREE = 2250a7bf1162db778b26a41d94e6e6f7d6b9480c
PARENT_1 = 072f1395ee310a876e93d633264f3ece43cecc3c
PARENT_2 = d7624753d9fa506bf3b4664ecfbad2af408d9834
POST_MERGE_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
```

`MERGE_TREE` equals authorized `#348` tree `2250a7bf`.
`ccacaa5` is an ancestor of `origin/main`.

```
AUTHORIZED_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

`src/`, `apps/`, `tests/`, `pyproject.toml` on `1983503` equal `ccacaa5`.

## Exact-main bounded validation (on `1983503`)

| Gate | Result |
| --- | --- |
| D-049 / D-063 / D-064 / D-067 focused | PASS (46 tests) |
| identity / connect smoke | PASS (33 tests) |
| source-lineage (`test_source_identity.py`) | PASS (included in identity set) |
| Control Plane | PASS (171 tests) |
| ruff | PASS |
| mypy | PASS (185 files) |
| Web typecheck (`tsc -b`) | PASS |
| Web build (`vite build`) | PASS |

```
NEW_HIGH = 0
HIGH_OPEN = 0
```

## Explicit non-claims

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
OWNER_AUTHORIZED_ROOT = <not yet supplied>
```

## Housekeeping plan executed after this seal

Unique evidence not on `main` remains on
`cursor/d049-final-reconciliation-6f85` (do not delete that branch):

- D-064 historical freeze/runbooks
- D-066 premerge receipts
- D-069 integration receipts
- D-071 / D-071A / D-072 packets

`#346` close as superseded by `#348`.
`#347` / `#349` close after this preservation proof.
`#350` remains the evidence hold for these receipts (or is closed only
after this commit is on the remote branch). Do not merge them onto main
as competing histories.
