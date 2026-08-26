# Prepared Local Windows packet — Atlas 3 `#592` (not dispatched)

Cloud must not claim Windows PASS. This packet is prepared only.
Do not send it to Local until `#516` D-LOCAL-AUG26-GE-WINDOWS-RESEAL-020
reaches a return gate, unless separate Local capacity is explicit.

```text
PR = 592
BRANCH = cursor/atlas-autonomous-night-cycle-at3058-dc2a
HEAD = 3f74bbb35bcb252727bab8e965b23c08b1194774
TREE = e73ec09e401c4279c4b71ff723925d7eae2c5cbe
EXPECTED_BASE_591 = 8c4c8a95dc7f04d5ba88d127e58aac161ebb00e6
LIVE_MAIN = f1b5256510cb66e037e6774aa49d753bdb7dd96f
AUTHENTIC_WINDOWS_PASS = UNCLAIMED
DISPATCHED_TO_LOCAL = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

This tests the **canonical tip**, not every stacked `#510`–`#591` PR.

## Checkout

```powershell
git fetch origin cursor/atlas-autonomous-night-cycle-at3058-dc2a
git checkout --detach 3f74bbb35bcb252727bab8e965b23c08b1194774
git rev-parse HEAD
git rev-parse HEAD^{tree}
# STOP if HEAD/TREE mismatch
```

## Scope (curator-independent)

Not Golden Estate. Do not run `atlas-golden-estate-curator` here.

```powershell
python -m atlas --help
python -m atlas version
# Atlas 3 CLI surfaces present on this tip (exact names from --help):
# pulse / start / proof / memory / ledger and any atlas3-registered parsers
$OutputEncoding = [Console]::OutputEncoding
chcp 1252
python -m pytest tests/unit/test_atlas3_*.py -q --tb=short --no-cov
```

Required Windows assertions:

- `atlas --help` and atlas3 CLI surfaces print under cp1252 without `UnicodeEncodeError`
- provider fixture ingest (Cursor/Codex fixtures already on the tip) succeeds or fail-closes honestly
- file/path semantics stay native; no POSIX-forced absolute Windows FS paths
- project isolation tests still pass
- `CODEX.md` / `AGENTS.md` are not treated as ingestion
- native-history API claims fail closed
- source mutation = 0 on fixture estates where the tests already assert it
- no Truth Core write
- secret echo = 0

STOP if HEAD/TREE moved. Do not merge. Do not treat Linux 540-pass as Windows PASS.
