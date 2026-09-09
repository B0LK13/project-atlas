# Formal IV request packet — AS-STUDIO-A2-006 (prepared; owner action to dispatch)

```text
PACKAGE_ID              = AS-STUDIO-A2-006
PR                      = #791
STATUS                  = PREPARED_AWAITING_OWNER_DISPATCH
FORMAL_IV               = NOT_STARTED
MERGE_AUTHORIZATION     = NOT_GRANTED
INHERITS_788_IV         = NO
INHERITS_4904125f_IV    = NO
```

## Freeze instruction

When exact-head CI is SUCCESS on a chosen tip, record:

```text
SUBJECT_HEAD            = <tip sha>
SUBJECT_TREE            = <tip tree>
CI_EXACT_HEAD           = <run id> SUCCESS
```

Do **not** treat CI success as Formal IV. Do **not** extend #788 / `4904125f` verdicts.

## Verifier checklist (adversarial)

1. Fingerprint identical for unchanged intent/decision when wall-clock differs.
2. Fingerprint changes when decision outcome changes.
3. Malformed decision never yields `PENDING_EXECUTE` or `CONFIRMED_SUCCESS`.
4. Malformed / wrong-schema intent never yields `CONFIRMED_SUCCESS` with a decision.
5. `--repo` with artifacts lacking repo fields → `MISMATCHED_BINDING` / `REPO_UNVERIFIED_IN_ARTIFACTS`.
6. Conflicting evidence vs decision file → `CONFLICTING_EVIDENCE`; auto_retry false.
7. Orphan `.tmp` alone → `INTERRUPTED_ATOMIC_WRITE`; `.tmp`+final → not interrupted; tmp not promoted.
8. Persistence-failed flag → no replay recommendation; auto_retry false.
9. `dependencies.task_context.state` and `control_plane_observation.state` are explicit (`UNAVAILABLE` on this stack).
10. Doctor `a2_006_*` PASS; unit tests under `test_atlas_studio_a2_006_mission_session.py` PASS.
11. Certified A2 tip `2debb778` untouched.

## Commands

```bash
git worktree add --detach /tmp/atlas-iv-a2-006 <SUBJECT_HEAD>
cd /tmp/atlas-iv-a2-006
export PYTHONPATH=scripts
python -m pytest tests/unit/test_atlas_studio_a2_006_mission_session.py -q --override-ini='addopts='
python scripts/atlas-studio.py doctor --json
```
