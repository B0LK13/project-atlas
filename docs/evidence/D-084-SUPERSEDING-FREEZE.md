# D-084 superseding freeze

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-D084-ESTATE-FAIR-SELECTION`
PACKAGE: `AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001` (same production lane as D-078 / D-080)
PR: `#351` (do not merge)

## Lineage

```
CURRENT_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
D080_PRODUCTION_FREEZE = 99aa937b3718cf0432bb688dbfa074daade7c049
D080_TREE = e73273f208009f9c317ffb489919e154938ee1c4
D081_AUTHENTIC_ESTATE_RUN_A = FAIL
D083 = TEST_ONLY PASS
```

D-080 remains a historical Local FAIL candidate. D-078 root policy and
D-080 container / knowledge-relation truth remain PASS and must not regress.
D-083 Windows CI portability remains valid.

## Production freeze (Local D-085 target)

```
D084_HEAD = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
D084_TREE = 4148e9a63de0089736bea1c0b2631dd1e4fe72e5
PRODUCTION_SEMANTIC_CHANGES_AFTER_D084_FREEZE = 0
```

Later evidence-only commits on this branch are not the Local IV target.

## D-081 authentic result (preserved)

```
D081_AUTHENTIC_ESTATE_RUN_A = FAIL
KNOWN_EXPECTED_FOUND = 3/5
A dark-factory = EMITTED
B playbook-platform = EMITTED
C black-agency-web-design = EMITTED
D vibed-dev-env = WALKED BUT SUPPRESSED
E onedrive-organizer = WALKED BUT SUPPRESSED
D:\tmp emitted = 252 / 500
DIRS_VISITED = 301473
ELAPSED = 01:17:19
```

## Root causes (not a D-078 policy failure)

```
D084_ROOT_CAUSE_1 = REGION_MONOPOLY_AFTER_INITIAL_BREADTH_PASS
D084_ROOT_CAUSE_2 = PROJECT_BOUNDARY_RANKING_INSUFFICIENT
D084_ROOT_CAUSE_3 = EXPENSIVE_ENRICHMENT_BEFORE_BOUNDED_SELECTION
D078_ROOT_POLICY = PASS
```

## What D-084 changed

`candidate_selection_policy = deterministic_hierarchical_fair_v2`

- Cheap sighting during traversal (path, depth, region, directory signals,
  git/worktree/marker boundary). No git-config / package / marker parse
  for every sighting.
- Hierarchical fair preselection: region round-robin, then family /
  boundary, then evidence, then path tie-break.
- Enrich only a shortlist of size `min(seen, emit_limit * 3)`.
- Final select from the enriched shortlist with the same allocator.
- Ancestor with an independent boundary is not displaced by a
  non-independent rich nested child.
- Independent nested repositories remain separately eligible.
- Family grouping still is not identity merge.

Not done (intentionally):

- hardcoded `D:\tmp` / owner project names / per-folder magic quotas
- a general traversal rewrite
- raising 500 → 5000

## Merge rule

```
MERGE_RECOMMENDATION = BLOCKED_PENDING_LOCAL_D085
AUTHENTIC_USER_ESTATE_ACCEPTANCE = FAIL
D_049_FINAL_ACCEPTANCE = FAIL
D_042_EXECUTION_GATE = CLOSED
```

## Next action

`LOCAL VALIDATE EXACT D084 FREEZE AGAINST AUTHENTIC D:\.`
