# D-080 superseding freeze

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-D080-CANDIDATE-SELECTION-TRUTH`
PACKAGE: `AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001` (same production lane as D-078)
PR: `#351` (do not merge)

## Lineage

```
CURRENT_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
D078_PRODUCTION_FREEZE = fcaf4f5e152b162a52bfc1c28654ff11acbeb842
D078_TREE = 119c779f8995ab576a231aaa06a334fb813cd737
D078_LOCAL_POLICY_REVALIDATION = PASS
D078_MERGE_CANDIDATE = SUPERSEDED_BY_D080
```

D-078 root policy remains historically validated and must stay PASS.
Do not merge D-078 alone.

## Production freeze (Local D-081 target)

```
D080_HEAD = 99aa937b3718cf0432bb688dbfa074daade7c049
D080_TREE = e73273f208009f9c317ffb489919e154938ee1c4
PRODUCTION_SEMANTIC_CHANGES_AFTER_D080_FREEZE = 0
```

Later evidence-only commits on this branch are not the Local IV target.

## D-079 authentic result (preserved)

```
D079_AUTHENTIC_ESTATE_RUN_A = PARTIAL
SCAN_COMPLETE = NO
TRUNCATION_CAUSES = max_depth_reached,project_and_knowledge_limits_reached
DIRS_VISITED = 301002
TOTAL_PROJECT_CANDIDATES = 500
KNOWN_EXPECTED_FOUND = 0/5
FALSE_PROJECT_MATCH_COUNT = 1   # D:/
FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS = 50
```

## Root causes (not a D-078 policy failure)

```
D080_ROOT_CAUSE_1 = CANDIDATE_LIMIT_STARVATION
D080_ROOT_CAUSE_2 = AUTHORIZED_VOLUME_ROOT_FALSE_PROJECT
D080_ROOT_CAUSE_3 = FALSE_KNOWLEDGE_PROJECT_ATTACHMENT
D078_ROOT_POLICY = PASS
```

## What D-080 changed

`TRAVERSAL ORDER != SELECTION AUTHORITY`

- Gather compact evidence for qualifying candidates during the walk.
- Select a deterministic bounded set by evidence weight, family diversity,
  and top-level region breadth. Canonical path is the tie-break only.
- Family grouping (`candidate_family`) affects output diversity only.
  `FAMILY_GROUPING != IDENTITY_MERGE`.
- Owner-authorized volume root is a scope container, never a project.
- Knowledge never attaches to blank, dangling, or scope-container ids.
- Cap honesty: seen / emitted / suppressed + `candidate_selection_policy`.
- D-067 `SCAN_COMPLETE` honesty is unchanged.

Not done (intentionally):

- raising 500 → 5000 / unlimited
- hardcoding the five owner anchors
- ignoring `worktrees` / `agent-development-projects` by name
- special-casing `D:\`
- creating `.atlas-project.yaml`
- a general performance rewrite

```
D078_TO_D080_PRODUCTION_DIFF =
  src/project_atlas/estate_discovery.py
  src/project_atlas/web_api/discovery.py
  apps/web/src/hooks/useEstateDiscovery.ts
  apps/web/src/pages/production/DiscoveryPage.tsx
  tests/unit/test_as_d049_080_candidate_selection.py
```

## Performance residual

```
D080_PERFORMANCE_RESIDUAL = NOT_MEASURED_ON_AUTHENTIC_ESTATE
```

D-079 measured ~301002 dirs / ~11 minutes. D-080 did not rewrite traversal.
Local D-081 must record `dirs_visited` and wall time on authentic `D:\`.

Max-depth remains a separate residual. D-079 proved the five anchors were
traversed; selection was the primary defect.

## Merge rule

```
MERGE_RECOMMENDATION = BLOCKED_PENDING_LOCAL_D081
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PARTIAL
D_049_FINAL_ACCEPTANCE = PARTIAL
D_042_EXECUTION_GATE = CLOSED
```

## Next action

`LOCAL VALIDATE EXACT D080 FREEZE AGAINST AUTHENTIC D:\.`
