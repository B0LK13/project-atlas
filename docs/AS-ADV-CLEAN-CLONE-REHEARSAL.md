# AS-ADV-CLEAN-CLONE-REHEARSAL-001 — Clean-clone RC rehearsal

| Field | Value |
|---|---|
| Mission | `AS-ADV-CLEAN-CLONE-REHEARSAL-001` |
| Directive | `D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001` |
| Existing authority | [AS-ADV-RELEASE-002](AS-ADV-RELEASE-002-clean-clone.md) |
| Existing matrix case | `clean_clone_replay` |
| Scope | Disposable fixture rehearsal only |

## Gate state

```text
RELEASE=NO
PILOT=NO
WEB ACCEPTED=NO
```

A passing rehearsal is operational RC evidence only. It does not claim
`RELEASE CERTIFIED`, authorize an estate pilot, accept the web application, or
permit production cutover.

## What the existing case proves

`atlas adv certify` already includes the AS-ADV-RELEASE-002
`clean_clone_replay` case. The case creates one synthetic source and one shared
discover manifest, initializes two independent disposable vaults, runs
`ingest` → `build-indexes` → `validate` on each, and compares the stable planes
(`projects/`, `state/`, `generated/indexes/`, and `00-system/`) byte-for-byte.
The full CLI matrix runs; this rehearsal then requires exactly one
`clean_clone_replay` row with `result: pass`.

This is a fixture clean-clone replay, not proof that a production estate can be
cloned, migrated, restored, or released.

## Operator procedure

1. Use a clean checkout of the intended RC commit. Record, but do not modify,
   the commit and tree pins:

   ```powershell
   git status --short
   git rev-parse HEAD
   git rev-parse "HEAD^{tree}"
   ```

2. Install the checkout in an isolated Python environment, or use an existing
   environment with the repository's development dependencies.
3. Run the fixture-safe helper from the repository root:

   ```powershell
   & .\.venv\Scripts\python.exe docs\scripts\adv_clean_clone_rehearsal.py
   ```

   Portable form:

   ```bash
   python docs/scripts/adv_clean_clone_rehearsal.py
   ```

4. Accept the rehearsal only when the command exits `0` and prints all four
   lines:

   ```text
   REHEARSAL=PASS case=clean_clone_replay result=pass
   RELEASE=NO
   PILOT=NO
   WEB ACCEPTED=NO
   ```

5. Preserve the terminal transcript with the recorded commit/tree pins as RC
   rehearsal evidence. Do not convert the result into a release, pilot, web
   acceptance, or production-cutover statement.

## Fixture-safety and failure behavior

The helper:

- creates its scratch tree with the operating system's temporary-directory API;
- accepts no estate root, vault root, report destination, or production path;
- invokes the checkout's `project_atlas.cli adv certify --json` implementation;
- passes no `--report-vault`, so no report is written into any vault;
- removes scratch data when the command returns;
- exits non-zero if the CLI fails, JSON is malformed, the clean-clone case is
  absent/duplicated/failing, or any non-claim flag is not exactly `false`.

On any non-zero exit, the result is `REHEARSAL=FAIL`; no partial output is
release evidence. The underlying report may use `status: certified` for its
fixture matrix status, but its authority plane remains `none` and its three
certification/acceptance booleans remain false.

## Direct CLI fallback

If the helper cannot run, an operator may invoke the existing CLI only with a
new disposable work root and JSON output:

```powershell
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("atlas-adv-" + [guid]::NewGuid())
try {
    & atlas adv certify --work-root $work --json
    if ($LASTEXITCODE -ne 0) { throw "atlas adv certify failed" }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
```

Do not supply an estate path or `--report-vault`. Verify the
`clean_clone_replay` row and all three false booleans before recording a pass.
The reviewed helper is preferred because it performs these checks fail-closed.
