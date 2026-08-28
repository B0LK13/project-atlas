---
name: atlas-golden-estate-curator
description: Discover, inventory, qualify, and recommend mature development projects as future Atlas acceptance-test estates. Default mode is read-only DISCOVER_ONLY. Never move, delete, rename, or modify source projects. Use when curating golden/challenge estates or scanning a disk of candidate projects.
---

# Atlas golden estate curator

Package: `ATLAS-GOLDEN-ESTATE-SKILL-001`  
This is **test-estate infrastructure**, not Atlas 3 Truth Core.

## Default safety

```text
DEFAULT_MODE = DISCOVER_ONLY
SOURCE_PROJECTS_ARE_EVIDENCE = YES
```

Forbidden by default (fail closed):

MOVE · DELETE · RENAME · SOURCE MODIFY · GIT CLEAN · GIT RESET ·
HISTORY REWRITE · AUTO COMMIT · AUTO PUSH · AUTO MERGE

COPY / GOLDENIZE require explicit owner authorization and are **not
implemented** in this skill version. Default execution stops at `OWNER_GATE`.

## Phases

```text
DISCOVER → INVENTORY → QUALIFY → RECOMMEND → OWNER_GATE
→ COPY → BASELINE_FREEZE → GOLDENIZE → INDEPENDENT_VERIFY → FREEZE_ESTATE
```

Implemented phases: DISCOVER through OWNER_GATE.  
Owner-gated phases: fail closed with `OWNER_GATE_REQUIRED`.

## Invocation

```bash
python atlas-vault-documentation/skills/atlas-golden-estate-curator/curator.py \
  --source-root <root> \
  --mode DISCOVER_ONLY \
  --phase RECOMMEND \
  --output /tmp/estate-report.json \
  --json
```

`--output` must be **outside** the source root. The report is derived evidence,
not a source mutation.

Windows D:\ first real run (Local only):

```powershell
python atlas-vault-documentation\skills\atlas-golden-estate-curator\curator.py `
  --source-root D:\ `
  --mode DISCOVER_ONLY `
  --phase RECOMMEND `
  --output $env:TEMP\atlas-golden-estate-d-drive.json `
  --json
```

`AUTHENTIC_D_DRIVE_TEST = LOCAL_WINDOWS_REQUIRED`. Cloud fixture certification
is not a D-drive pilot pass.

## Qualification (objective signals only)

No subjective trust scores. Record only:

- git / non-git / nested-repo / monorepo
- dirty worktree
- missing README
- stale docs (README older than src)
- test/build failure **signals** (never execute project tests or build scripts)
- secret-shaped filenames/content (metadata only; never echo secrets)
- symlink / junction escape
- duplicate project identity
- generated directories (skipped)

## Outputs

inventory · qualification report · candidate table · security exclusions ·
disk estimate · recommended golden set · recommended challenge set

## Honesty

```text
PREP != IMPLEMENTED for COPY/GOLDENIZE
CLOUD_FIXTURE != AUTHENTIC_D_DRIVE
SKILL != TRUTH CORE
SOURCE MUTATION = 0 in DISCOVER_ONLY
```

Load [references/SAFETY.md](references/SAFETY.md), [references/PHASES.md](references/PHASES.md),
[references/WINDOWS-D-DRIVE.md](references/WINDOWS-D-DRIVE.md), and
[references/QUALIFICATION.md](references/QUALIFICATION.md).
