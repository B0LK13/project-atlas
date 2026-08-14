# Local D-081 revalidation runbook

Target exact D-080 production freeze. Do not validate an evidence-only tip.

```
HEAD = 99aa937b3718cf0432bb688dbfa074daade7c049
TREE = e73273f208009f9c317ffb489919e154938ee1c4
```

```bash
git fetch origin cursor/d049-authorized-volume-root-6f85
git checkout 99aa937b3718cf0432bb688dbfa074daade7c049
test "$(git rev-parse HEAD^{tree})" = "e73273f208009f9c317ffb489919e154938ee1c4"
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

## 4. Verify the five owner anchors are emitted

Required names (not hardcoded in product code; Local acceptance target):

- `dark-factory`
- `playbook-platform`
- `black-agency-web-design`
- `vibed-dev-env`
- `onedrive-organizer`

```
KNOWN_EXPECTED_FOUND = 5/5
```

If any is absent solely because the output cap starved it → FAIL.

Do not require all 168 observed directories or the ≈55 estimate.

## 5. Inspect candidate-family pressure

- `scan.project_candidates_seen` / `emitted` / `suppressed`
- `candidate_selection_policy = deterministic_bounded_v1`
- worktree/copy families must not occupy the entire emitted set
- `FAMILY_GROUPING != IDENTITY_MERGE` (no silent identity merge)

## 6. `D:\` is not a project

```
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
```

## 7. Blank / dangling knowledge relations

```
EMPTY_PROJECT_ID_ASSIGNMENTS = 0
DANGLING_PROJECT_RELATIONS = 0
BLANK_PROJECT_RELATIONS = 0
```

Root-level knowledge may be unmatched/ambiguous/reviewable. It must not be
assigned to an invented root project.

## 8. Freeze Run A

Preserve D-079 PARTIAL as historical truth. This is a new run against a new
freeze. Record:

- `DIRS_VISITED`
- wall time (`D080_PERFORMANCE_RESIDUAL`)
- `SCAN_COMPLETE` (must stay honest; do not require YES)
- truncation causes
- the five anchors

## 9. Run B only after Run A can emit the five anchors

D-079 Run B was `UNCHANGED` because selection starvation masked the
documentation experiment. Do not conclude documentation optimization has
no value. Restore D-075 optimized docs and rerun Run B only after Run A
emits the anchors.

## Out of scope

- D-042 (`D_042_EXECUTION_GATE = CLOSED`)
- merging #351
- raising the 500 cap as the fix
- Documentation Health / Living Roadmap / Project Memory / Momentum /
  Portfolio / 2.3 / OPT / AutoLab / Prime
