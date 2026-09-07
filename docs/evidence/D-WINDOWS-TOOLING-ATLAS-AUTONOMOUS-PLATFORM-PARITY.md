# D-WINDOWS-TOOLING-ATLAS-AUTONOMOUS-PLATFORM-PARITY

Date: 2026-09-07  
Repository: `B0LK13/project-atlas`  
Branch: `chore/windows-tooling-parity-705`

## Scope

Windows tooling parity for the #705 tooling lane, without mutating production
runtime packages under `src/project_atlas`.

## Implemented changes

- Added Windows bootstrap script: `scripts/bootstrap-dev-tooling.ps1`
  - modes: `-Check`, `-DryRun`, `-Install`
  - detect-before-install and no forced upgrades
  - user-scope install preference via npm/pipx/winget
- Added Windows health reporter: `scripts/check-windows-dev-health.ps1`
  - read-only JSON machine report
  - no token extraction commands
- Extended canonical tooling manifest to cross-platform metadata:
  - `development-tooling-manifest.json`
  - platform-aware install methods and config locations
- Added Windows bootstrap guidance:
  - `docs/tooling/windows-development-bootstrap.md`
- Normalized Linux-host docs to avoid hardcoded user paths and clarify
  Linux-vs-Windows boundaries:
  - `docs/tooling/atlas-development-bootstrap.md`
  - `docs/tooling/mcp-health-and-permissions.md`
  - `docs/tooling/post-merge-activation-checklist-pr705.md`
  - `docs/tooling/CODEBASE_MEMORY_BASELINE.md`
- Added Windows-oriented test coverage:
  - `experiments/agents_sdk/tests/test_bootstrap_script_windows.py`
  - updated `experiments/agents_sdk/README.md` with PowerShell run commands

## Validation run

```text
pwsh parser check: scripts/bootstrap-dev-tooling.ps1 -> PASS
pwsh parser check: scripts/check-windows-dev-health.ps1 -> PASS
uv run --python 3.12 --extra dev -m pytest -q experiments/agents_sdk/tests/test_bootstrap_script_pinning.py experiments/agents_sdk/tests/test_bootstrap_script_windows.py experiments/agents_sdk/tests/test_lab.py experiments/agents_sdk/tests/test_evals_contract.py -> PASS
jq empty development-tooling-manifest.json -> PASS
bootstrap-dev-tooling.ps1 -Check -> PASS
bootstrap-dev-tooling.ps1 -DryRun -> PASS
bootstrap-dev-tooling.ps1 second -Check consistency -> PASS
secret literal regex scan over changed files -> 0 findings
```

## Security and authority boundaries

- No plaintext tokens were added.
- GitHub MCP is documented as runtime-auth (`gh auth`) only.
- Codebase Memory is explicitly documented as derived intelligence, not
  canonical merge/verification evidence.
- `src/project_atlas/**` unchanged in this lane.

## Known limitations

- This run executed in Linux/WSL host context; native Windows runtime
  collection (Windows edition/build, `winget`, `py -3.12`, native client MCP
  invocations) remains pending and must be executed on a native Windows host.
- Figma integration remains manual-auth gated.
- Independent verification is still required before merge authorization.
