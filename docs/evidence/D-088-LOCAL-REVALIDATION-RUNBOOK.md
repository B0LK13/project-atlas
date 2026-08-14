# Local D-088 revalidation runbook

Target exact D-087 production freeze. Do not validate an evidence-only tip.

```
HEAD = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
TREE = 14318297c5fbf40b4fff054ad27126ee4c89db7f
```

```bash
git fetch origin cursor/d049-authorized-volume-root-6f85
git checkout b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
test "$(git rev-parse HEAD^{tree})" = "14318297c5fbf40b4fff054ad27126ee4c89db7f"
```

If HEAD/TREE differ → `VALIDATION_STALE`. Stop.

Do **not** merge #351 before this run.

## 1. Repeat D-078 policy probes

1. `atlas discover --root D:\` → `FILESYSTEM_ROOT_NOT_ALLOWED`
2. `atlas discover --root D:\ --root-mode owner-authorized-volume --json` → accept
3. `atlas discover --root C:\ --root-mode owner-authorized-volume` → `SYSTEM_VOLUME_ROOT_NOT_ALLOWED`
4. External reparse/junction from `D:\` is not followed

## 2. Reconstruct original D-075 docs safely

Local only. Cloud must not modify the five external repositories.
Do this reconstruction before Run A if the D-075 baseline is not already
present. Do **not** start Run B unless Run A is PASS.

## 3. Authentic Run A — volume root only

```
atlas discover --root D:\ --root-mode owner-authorized-volume --vault <vault>
```

Do not substitute `D:\dev-ai`, five project roots, or any invented aggregate.
Do not give Atlas individual project roots.

## 4. Five owner anchors must be emitted

Required names (not hardcoded in product code; Local acceptance target):

- `dark-factory`
- `playbook-platform`
- `black-agency-web-design`
- `vibed-dev-env`
- `onedrive-organizer`

```
KNOWN_EXPECTED_PROJECTS = 5
KNOWN_EXPECTED_FOUND = 5/5
PROJECT_DISCOVERY_RECALL_KNOWN = 5/5
OWNER_ANCHORS_STARVED_BY_CAP = 0
```

If any is walked but suppressed by the output cap → FAIL.

`vibed-dev-env` must be emitted even if a nested `vibed_setup` (or similar
non-independent child) is richer. `onedrive-organizer` must be emitted even
if another `dev-cloud` sibling was selected earlier.

## 5. Distribution and policy

```
candidate_selection_policy = deterministic_hierarchical_fair_v2
NOISY_SUBTREE_MONOPOLY = NO
```

Record:

- `project_candidates_seen` / `preselected` / `enriched` / `emitted` / `suppressed`
- `knowledge_candidates_seen` / `emitted` / `suppressed`
- `region_candidate_counts` and `region_emitted_counts`
- `scan.operation_counters` (non-authoritative)
- `scan.path_resolve_calls_during_in_memory_selection` (expect `0`)
- `D:\tmp` (or equivalent noisy top-level) must not consume the bounded
  output while other active regions still have eligible projects

`FAMILY_GROUPING != IDENTITY_MERGE`.

## 6. Root-container and knowledge truth

```
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
EMPTY_PROJECT_ID_ASSIGNMENTS = 0
DANGLING_PROJECT_RELATIONS = 0
BLANK_PROJECT_RELATIONS = 0
VOLUME_CONTAINER_PROJECT_RELATIONS = 0
FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS = 0
SILENT_IDENTITY_MERGES = 0
SILENT_KNOWLEDGE_MISASSIGNMENT = 0
PATH_ESCAPES = 0
```

## 7. Performance

Record `dirs_visited`, wall time, phase diagnostics if present in the
process/stderr or in-memory report (`_perf` is stripped from the written
JSON), and `scan.operation_counters`.

Compare with:

```
D079 ≈ 00:10:59 / ~301002 dirs
D081 = 01:17:19 / 301473 dirs
D085 = 01:22:01 / 301752 dirs
```

Do not invent a magic minute threshold.

Classify `D087_PERFORMANCE_RESIDUAL` from:

- absolute usability of a first authentic scan
- relative improvement versus D079 / D081 / D085
- phase diagnostics
- dirs visited
- candidate cardinalities
- whether the remaining cost is intrinsic first-scan traversal

Required:

```
D087_PERFORMANCE_RESIDUAL != SEVERE
```

If correctness is 5/5 but runtime remains severe:

```
D087_PERFORMANCE_RESIDUAL = SEVERE
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PARTIAL
D_049_FINAL_ACCEPTANCE = PARTIAL
```

Do not silently accept SEVERE for final D-049 closure.

Expected Cloud-side structural signals (not authentic wall-clock):

```
PATH_RESOLVE_CALLS_DURING_IN_MEMORY_SELECTION = 0
KNOWLEDGE_PROJECT_ANCESTRY_CHECKS << K * P
```

## 8. Run B

Only if Run A is PASS (`KNOWN_EXPECTED_FOUND = 5/5` and
`D087_PERFORMANCE_RESIDUAL != SEVERE`). Do not waste another full estate
scan if performance remains a blocker.

Run B is the D-075 documentation comparison only.

## 9. Report

Return CASE A PASS / CASE B PARTIAL / CASE C FAIL with the smallest
remaining blocker. Do not merge.

```
MERGE_AUTHORIZATION = NOT_GRANTED
D_042_EXECUTION_GATE = CLOSED
```
