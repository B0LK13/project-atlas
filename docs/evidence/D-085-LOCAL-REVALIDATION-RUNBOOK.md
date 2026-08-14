# Local D-085 revalidation runbook

Target exact D-084 production freeze. Do not validate an evidence-only tip.

```
HEAD = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
TREE = 4148e9a63de0089736bea1c0b2631dd1e4fe72e5
```

```bash
git fetch origin cursor/d049-authorized-volume-root-6f85
git checkout 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
test "$(git rev-parse HEAD^{tree})" = "4148e9a63de0089736bea1c0b2631dd1e4fe72e5"
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

## 3. Authentic Run A — volume root only

```
atlas discover --root D:\ --root-mode owner-authorized-volume --vault <vault>
```

Do not substitute `D:\dev-ai`, five project roots, or any invented aggregate.

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
```

## 7. Performance

Record `dirs_visited`, wall time, `project_candidates_seen`,
`project_candidates_enriched`.

Compare with:

```
D079 ≈ 11 min / ~301002 dirs
D081 = 77 min / 301473 dirs
```

Do not invent an absolute minute target. If correctness is 5/5 but runtime
remains severe:

```
D084_PERFORMANCE_RESIDUAL = SEVERE
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PARTIAL
```

Do not silently accept SEVERE for final D-049 closure.

If `project_candidates_seen` >> emitted, `project_candidates_enriched`
must be substantially less than seen.

## 8. Run B

Only if Run A is PASS and performance does not make the experiment
impractical. Do not spend another 77-minute run while Run A is blocked.

## 9. Report

Return CASE A PASS / CASE B PARTIAL / CASE C FAIL with the smallest
remaining blocker. Do not merge.
