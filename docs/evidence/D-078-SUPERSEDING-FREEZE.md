# D-078 superseding freeze

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-DEV-VOLUME-ROOT-078`
PACKAGE: `AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001`

## Historical truth (do not rewrite)

Local authentic Run A against `main` `198350319c17b4de0665f972fda0bc51420cd686`
refused owner-authorized `D:\` as a filesystem root.

```
LOCAL_RUN_A_198350319 = FAIL
FAILURE_CLASS = DISCOVERY_DEFECT
FAILURE_REASON = AUTHORIZED_ROOT_REFUSED_FILESYSTEM_ROOT
AUTHORIZED_ROOT = D:\
SCAN_STARTED = NO
PATH_ESCAPES = 0
NEW_HIGH = 0
AUTHENTIC_USER_ESTATE_ACCEPTANCE = FAIL
D_049_FINAL_ACCEPTANCE = FAIL
```

That FAIL remains historical truth. This freeze is a **new** candidate for a
**new** authentic run. It does not convert Run A into PASS.

Classification: **PRODUCT BLOCKER / D-049 ACCEPTANCE BLOCKER**.
`NEW_SECURITY_HIGH = 0` (current `main` fails safe).

## Production freeze (Local IV target)

```
D078_HEAD = fcaf4f5e152b162a52bfc1c28654ff11acbeb842
D078_TREE = 119c779f8995ab576a231aaa06a334fb813cd737
PARENT = 198350319c17b4de0665f972fda0bc51420cd686
BRANCH = cursor/d049-authorized-volume-root-6f85
PR = #351
```

Later evidence-only commits on this branch must not be treated as the Local
IV target. `PRODUCTION_SEMANTIC_CHANGES_AFTER_FREEZE = 0`.

## Contract

```
DEFAULT: filesystem root discovery = REFUSED
EXPLICIT OWNER_AUTHORIZED_VOLUME_ROOT: Windows non-system volume root = ALLOWED
```

CLI:

```
atlas discover --root D:\ --root-mode owner-authorized-volume
```

Not `--unsafe` / `--force` / `--ignore-safety`.

Still refused even with explicit mode:

- Windows system volume (`C:\`) → `SYSTEM_VOLUME_ROOT_NOT_ALLOWED`
- home directory → `HOME_DIRECTORY_NOT_ALLOWED`
- Linux/macOS `/` → `FILESYSTEM_ROOT_NOT_ALLOWED`
- UNC/network roots → `UNC_VOLUME_ROOT_NOT_ALLOWED`
- non-root directory + volume mode → `VOLUME_MODE_REQUIRES_WINDOWS_VOLUME_ROOT`
  (no silent reinterpret as bounded-directory)

Volume authorization permits traversal/discovery only.

`DISCOVER != CONNECT != INGEST != TRUST != AUTHORITY`

## Report honesty

Discovery reports expose:

- `authorized_root`
- `authorized_root_mode` (`BOUNDED_DIRECTORY` | `OWNER_AUTHORIZED_VOLUME_ROOT`)
- `volume_root_authorized`
- `volume_root_kind` (`NON_SYSTEM_WINDOWS_VOLUME` | `NONE`)
- `scan.scan_complete` / `truncation_causes`

CLI/API/Web must not present an exceptional volume scan as an ordinary
bounded-directory scan.

## Merge rule

```
MERGE_RECOMMENDATION = BLOCKED_PENDING_LOCAL_REVALIDATION
D_042_EXECUTION_GATE = CLOSED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = FAIL
D_049_FINAL_ACCEPTANCE = FAIL
```

Required before any merge eligibility:

- Cloud D-078 implementation + Cloud IV PASS (this freeze)
- Local policy probes on exact `D078_HEAD` / `D078_TREE`
- Local authentic Run A against `D:\` using **only** the explicit
  owner-authorized volume contract (no invented subdirectory aggregate)
- `HIGH_OPEN = 0`

## Next action

`LOCAL REVALIDATE EXACT D078 FREEZE AGAINST OWNER-AUTHORIZED D:\.`
