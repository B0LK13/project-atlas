# Windows D:\ local runbook

Cloud cannot perform authentic `D:\` estate discovery.

```text
AUTHENTIC_D_DRIVE_TEST = LOCAL_WINDOWS_REQUIRED
CLOUD_FIXTURE != AUTHENTIC_D_DRIVE
```

## Exact first real run

```text
SOURCE_ROOT = D:\
MODE = DISCOVER_ONLY
PHASE = RECOMMEND
```

Expected: READ_ONLY. No copies. No moves. No goldenization.

```powershell
python atlas-vault-documentation\skills\atlas-golden-estate-curator\curator.py `
  --source-root D:\ `
  --mode DISCOVER_ONLY `
  --phase RECOMMEND `
  --output $env:TEMP\atlas-golden-estate-d-drive.json `
  --json
```

The report path must stay off `D:\` if `D:\` is the source root
(`$env:TEMP` is acceptable).

## Expected artifacts

- inventory
- qualification report
- candidate table
- security exclusions
- disk estimate
- recommended golden set
- recommended challenge set

## Do not

- `--phase COPY` / `--phase GOLDENIZE`
- `--action DELETE` / `MOVE` / `GIT_CLEAN`
- run discovered `build.sh` / test suites
- mark this cloud certification as a D-drive pilot pass
