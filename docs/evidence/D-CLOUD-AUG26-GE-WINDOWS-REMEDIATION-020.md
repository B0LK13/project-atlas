# D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020 — exact-object successor seal

Canonical PR: `#516` (`cursor/atlas-golden-estate-inventory-honesty-7f43`).
No replacement PR. No merge. Certification is not transferred from the failed SHA.

```text
DIRECTIVE = D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020
PR = 516
PR516_OLD_HEAD = 0c32f69d4a1b7da582f93a796c5b4bd9c81c20e7
PR516_OLD_TREE = 7b9be18d4f6495f2ddf0b843e25f8f63dcfc4a34
LIVE_MAIN_HEAD = f1b5256510cb66e037e6774aa49d753bdb7dd96f
LIVE_MAIN_TREE = 8df56184bb25b1cf1b6a9102cf34e77248287940
BASE_HEAD = f1b5256510cb66e037e6774aa49d753bdb7dd96f
BASE_TREE = 8df56184bb25b1cf1b6a9102cf34e77248287940
TARGET_MOVED = YES
IV_BOUND_HEAD = 911c3944ef5944f89b3c1532ec7ed33da90beb84
IV_BOUND_TREE = 605123fce29744a73c52e2149ba9d8ca5535260a
GE_WIN_001 = PASS
GE_WIN_002_SYNTHETIC = PASS
FULL_SKILL_SUITE = 48 passed
RUFF = PASS
MYPY = PASS
INDEPENDENT_IV = PASS
VERIFIER_ID = IV-GE-WIN-020E
P0 = 0
P1 = 0
P2 = AUTHENTIC_D_DRIVE_UNCLAIMED; PATHLIB_1921_SWALLOW; SKIP_BY_NAME_GENERATED; OUTPUT_MKDIR; ISOLATED_QUALIFY_CALLER_DICT; GIT_SUBPROCESS_FAILURE; README_BODY_UNREAD; GITDIR_EXISTS_NONE_SWALLOW
SOURCE_MUTATIONS = 0
SECRET_ECHO = 0
COPY_AUTHORIZED = NO
GOLDENIZE_AUTHORIZED = NO
AUTHENTIC_D_DRIVE_PASS = UNCLAIMED
AUTHENTIC_D_DRIVE_RETEST_REQUIRED = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`NEW_HEAD` / `NEW_TREE` are the docs-only successor that includes this seal.
Independent IV bound `911c3944ef5944f89b3c1532ec7ed33da90beb84` /
`605123fce29744a73c52e2149ba9d8ca5535260a`. Curator code is unchanged after that bind.

## Changed paths (this remediation wave)

- `atlas-vault-documentation/skills/atlas-golden-estate-curator/curator.py`
- `atlas-vault-documentation/skills/atlas-golden-estate-curator/tests/test_windows_remediation.py`
- `atlas-vault-documentation/skills/atlas-golden-estate-curator/tests/test_inventory_honesty.py`
- `atlas-vault-documentation/skills/atlas-golden-estate-curator/references/SAFETY.md`
- `atlas-vault-documentation/skills/atlas-golden-estate-curator/references/WINDOWS-D-DRIVE.md`
- `atlas-vault-documentation/skills/atlas-golden-estate-curator/references/QUALIFICATION.md`
- `WORKLOG.md`
- `docs/evidence/D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020.md`
- `docs/evidence/D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020-LOCAL-REBIND.md`

## Honesty

```text
INACCESSIBLE != SAFE
INACCESSIBLE != GOLDEN
SKIPPED != SCANNED
PARTIAL_DISCOVERY != COMPLETE_DISCOVERY
INTERNAL_FILESYSTEM_PATH = PLATFORM_NATIVE
REPORT_RELATIVE_IDENTITY = POSIX_STYLE
CLOUD_FIXTURE != AUTHENTIC_D_DRIVE
IMPLEMENTER_TESTS != IV
```

All evidence before `NEW_HEAD` is superseded. The failed exact object
`0c32f69d` / `7b9be18d` is not a certification transfer source.
