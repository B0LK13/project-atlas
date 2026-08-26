# Local rebind packet — Golden Estate #516 successor only

Local must rerun **only** Golden Estate `#516` successor acceptance.
Do **not** rerun `#511`, `#601`, `#602`, or `#603` unless those exact
tested objects have moved.

## Preserved Local seals (exact-object only; invalidate on movement)

```text
#511  156ae7e4... / 9733f996...   AUTHENTIC_WINDOWS_PASS = YES
#601  c1d59389...                 AUTHENTIC_WINDOWS_PASS = YES
#602  04c0ea84...                 AUTHENTIC_WINDOWS_PASS = YES
#603  0e66476d...                 AUTHENTIC_WINDOWS_PASS = YES
```

## Exact #516 successor object

Fill `NEW_HEAD` / `NEW_TREE` from the commit that added this packet
(`git rev-parse HEAD` / `git rev-parse 'HEAD^{tree}'` on
`cursor/atlas-golden-estate-inventory-honesty-7f43` after pull).

Independent IV bound (curator code identical):

```text
PR = 516
BRANCH = cursor/atlas-golden-estate-inventory-honesty-7f43
IV_BOUND_HEAD = 911c3944ef5944f89b3c1532ec7ed33da90beb84
IV_BOUND_TREE = 605123fce29744a73c52e2149ba9d8ca5535260a
FAILED_EXACT_HEAD = 0c32f69d4a1b7da582f93a796c5b4bd9c81c20e7
FAILED_EXACT_TREE = 7b9be18d4f6495f2ddf0b843e25f8f63dcfc4a34
```

## Exact checkout

```powershell
git fetch origin cursor/atlas-golden-estate-inventory-honesty-7f43
git checkout cursor/atlas-golden-estate-inventory-honesty-7f43
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

STOP if `HEAD`/`TREE` do not match the pushed successor (docs-only
delta after `911c3944ef5944f89b3c1532ec7ed33da90beb84` is expected;
curator `.py` must match that bind). Do not test `0c32f69d`.

## Exact Golden Estate skill command

```powershell
python -m pytest atlas-vault-documentation/skills/atlas-golden-estate-curator/tests -q --tb=short --no-cov -o addopts=
```

Expect: `FAILED_TESTS = 0` (Cloud last saw 48 passed).

## Exact authentic D:\ curator command

```powershell
python atlas-vault-documentation\skills\atlas-golden-estate-curator\curator.py `
  --source-root D:\ `
  --mode DISCOVER_ONLY `
  --phase RECOMMEND `
  --output $env:TEMP\atlas-golden-estate-d-drive.json `
  --json
```

Expected report location: `$env:TEMP\atlas-golden-estate-d-drive.json`
(must stay off `D:\`).

## Expected exclusion / identity semantics

- Report-relative identities use `/` (`GE-WIN-001`).
- Inaccessible junction/reparse/permission descendants emit closed
  `INACCESSIBLE_PATH`, `inspected=false`, and siblings continue
  (`GE-WIN-002`).
- Root-level inability to inspect `D:\` itself is terminal.
- `discovery.complete` is false when any `INACCESSIBLE_PATH` exists.
- `INACCESSIBLE != SAFE != GOLDEN`. `SKIPPED != SCANNED`.

## Mutation-fingerprint requirements

```text
source_mutations == 0
files_moved == 0
files_deleted == 0
copy_authorized == false
goldenize_authorized == false
SECRET_ECHO == 0
COPY_AUTHORIZED == NO
GOLDENIZE_AUTHORIZED == NO
```

Do not run `--phase COPY`, `--phase GOLDENIZE`, `--action DELETE`,
`--action MOVE`, or `--action SOURCE_MODIFY`.

## GE-WIN-001 assertion

If the estate contains a nested relative project that would have
serialized as `group-a\widget` on the failed SHA, the successor report
must contain `group-a/widget` and must not persist `group-a\widget`
in `inventory.path`, `duplicate_of`, `generated_directories`,
`exclusions[].path`, qualification / candidate-table paths, or
recommendation sets. Absolute `source_root` / `report_path` stay
Windows-native.

## GE-WIN-002 assertion

An inaccessible junction/reparse/permission descendant must not abort
the `D:\` inventory. The report must still be written. Valid siblings
must still be discovered. The inaccessible object must not appear in
`recommended_golden_set`. `source_mutations` remains 0.

## Stop / failure conditions

- STOP if `#516` HEAD/TREE moved away from the fetched successor
  (other than this docs-only seal).
- FAIL if pytest has any failure.
- FAIL if curator crashes on an inaccessible descendant (P1).
- FAIL if report-relative paths contain `\`.
- FAIL if an inaccessible object is golden/recommended.
- FAIL if `source_mutations != 0` or secrets are echoed.
- FAIL if COPY/GOLDENIZE/DELETE/SOURCE_MODIFY succeed.
- Do not claim merge authorization.

```text
AUTHENTIC_D_DRIVE_RETEST_REQUIRED = YES
AUTHENTIC_D_DRIVE_PASS is Local-only after this run
MERGE_AUTHORIZATION = NOT_GRANTED
```
