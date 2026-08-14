# D-069 D-049 integration lineage (prepared, not applied to #346)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-INTEGRATION-069`

This receipt is **current state**. It does not rewrite historical D-063 / D-064
freeze documents. Those remain valid as contemporaneous records of invalidated
candidates.

## Lifecycle truth (do not collapse)

```
9c71cc2 / 10539a86     D-063 candidate     INVALIDATED by D-064 evidence
0509287 / 728f3af      D-064 candidate     INVALIDATED by D-065 Windows IV
ccacaa5 / d26768       D-067 candidate     CURRENT semantic production freeze
```

```
D065_WINDOWS_IV = FAIL
D065_HIGH_COUNT = 2

D067_SUPERSEDING_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
D067_SUPERSEDING_TREE = d26768fe753c888cd45001987da2afe977c79d45
D067_CI = PASS
D067_CI_RUN = 31779400311

LOCAL_D068_TARGET_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
LOCAL_D068_TARGET_TREE = d26768fe753c888cd45001987da2afe977c79d45
LOCAL_D068_REVALIDATION = IN_PROGRESS

D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
```

Branch tip is **not** the Local target. Local stays pinned to `ccacaa5`.

## Divergence that this lineage reconciles

```
0509287
  ├─ docs-only ── d3a9458   (#346 current tip)
  └─ D-067 prod ── ccacaa5  (Local D-068 target)
                    └─ docs-only ── D-067 receipts
```

`PR_D067_RELATION = DIVERGED` at `0509287`.

`ccacaa5` is **not** an ancestor of #346 tip `d3a9458`.

## Integration strategy

Merge commit of D-064 evidence lineage onto `ccacaa5`, then replay D-067
evidence. #346 ref was **not** moved.

```
INTEGRATION_STRATEGY = MERGE_EVIDENCE_ONTO_CCACAA5
MERGE_COMMIT = 7165a768e509277b3b0aadb43757ca362ff38ca0
MERGE_PARENTS = ccacaa5bcb094f35017c7195264fef55e382cb49
                d3a9458f478c3c06be0086622c3f262ec9938175
```

```
INTEGRATION_BRANCH = cursor/d049-integration-lineage-6f85
D069_RECEIPT_COMMIT = a25c428c4441be43b90dd49f4e71b8e1cc7df33e
D069_RECEIPT_TREE = 9c26d9301f640e96664afd4b4016a69b0e73b6e5
```

`INTEGRATION_HEAD` / `INTEGRATION_TREE` are the tip of
`cursor/d049-integration-lineage-6f85` after this pin (evidence-only).
That tip remains a descendant of `ccacaa5` with production trees identical
to the D-067 freeze. #346 ref was **not** moved.

## Local applicability proof

For every production-semantic tree:

| Path | `ccacaa5` blob/tree | integration blob/tree | Equal |
| --- | --- | --- | --- |
| `src/` | `62d346252197c8812f933e0e09e6ddba602b0f59` | same | YES |
| `apps/` | `6a9938729fac2a07542298586a171f7070a31dda` | same | YES |
| `tests/` | `e5fef7136f71b3308a5feba003c59b4a774b57f1` | same | YES |
| `pyproject.toml` | `9a7729d2e465d1855bf49aa7d1c119874120d48e` | same | YES |

`git diff ccacaa5..INTEGRATION -- src apps tests pyproject.toml` is empty.

Therefore:

```
LOCAL_TESTED_PRODUCTION_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
INTEGRATION_PRODUCTION_SEMANTICS = IDENTICAL_TO_CCACAA5
LOCAL_RESULT_APPLICABLE_TO_INTEGRATION_TIP = YES
```

Local D-068 does **not** need rerun solely because evidence-only commits
sit above the semantic freeze.

## Path classification (`ccacaa5` → integration tip)

All changed paths are under `docs/evidence/` (D-063/D-064 historical
receipts, D-064 overnight results, D-067 receipts, this D-069 receipt).

```
PRODUCTION_SEMANTIC_PATHS_CHANGED = 0
UNCLASSIFIED_PATHS = 0
EVIDENCE_HISTORY_PRESERVED = YES
STALE_GOVERNANCE_RECONCILED = YES
```

Stale "0509287 is current Local target" text remains in historical D-064
receipts as contemporaneous truth. Current state is this D-069 receipt.

## What this does not do

- Does not amend `ccacaa5`
- Does not move `cursor/d049-knowledge-estate-discovery-d036` (#346)
- Does not merge #346
- Does not start D-042
- Does not invent an authentic estate
