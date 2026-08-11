# REMEDI — CLAUDE-ADV005-002 / CLAUDE-ADV005-011

| Field | Value |
|---|---|
| Tip base | `b0d4413cc5591a9cc789101db95b3f2cd3621afe` |
| Branch | `remedi/adv005-claude-002-011` |
| WT | `D:\atlas-worktrees\adv005-w6-remedi-294` |
| #291 | **UNTOUCHED** |
| Features | **NO** |
| MERGE | **NO** until dual IV |
| EXTERNAL_SECURITY_REVALIDATION_REQUIRED | **YES** |
| CODEX_VALIDATED | **NO** |

## Findings

| ID | Claude sev | Cursor repro | Remedi |
|---|---|---|---|
| CLAUDE-ADV005-002 | CRIT | **REPRODUCED** (W1 + remedi probe) | Fail-closed final-path TIP_LOCAL |
| CLAUDE-ADV005-011 | HIGH | Gap clear in tip `Ensure-AtlasEditableInstall` PATH return (W2 pending); fixed fail-closed | Refuse foreign PATH `atlas.exe`; bind tip `.venv\Scripts` only |

## Fix summary

1. **CLAUDE-002:** `Resolve-AtlasFinalPath` via Win32 `GetFinalPathNameByHandleW`. `Test-AtlasPathUnderRoot` compares **final** targets. `Test-AtlasInterpreterIsTipVenv` requires lexical under `RepoRoot\.venv` **and** final under `RepoRoot` (never trusts `TipLocal` alone). `Ensure-AtlasTipLocalVenv` refuses junction/reparse `.venv` escape.
2. **CLAUDE-011:** Removed post-install `return $atlasCmd.Source` PATH fallback. Live serve binds tip `.venv\Scripts\atlas.exe` only.

## Evidence

| Artifact | Result |
|---|---|
| `env-iso-selftest.txt` | PASS (CaseG junction refuse, CaseH PATH refuse contract) |
| `junction-refuse-probe.txt` | `REFUSE_JUNCTION=True` |
| `path-refuse-probe.txt` | `PATH_REFUSE_SOURCE=True`; `HAS_RETURN_ATLASCMD_SOURCE=False` |
| W1 repro | `CLAUDE-REPRO-002` disposition REPRODUCED / FINAL_SEV=CRITICAL |

## Flags

| Flag | Value |
|---|---|
| EXTERNAL_SECURITY_REVALIDATION_REQUIRED | **YES** |
| CODEX_VALIDATED | **NO** |
| PR_MERGE | **BLOCKED** until dual independent IV |
