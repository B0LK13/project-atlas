# Windows Development Bootstrap (Tooling Lane)

Status: non-production developer tooling guidance for Windows hosts.

## Scope and boundaries

- Tooling lane only. No production Atlas runtime mutation.
- Use Python 3.12 for Windows CI-equivalent Atlas work.
- MCP tokens must be runtime-injected and never stored literally in tracked files.
- Codebase Memory is derived developer intelligence, not canonical merge authority.

## Canonical paths (Windows)

- Copilot MCP config: `$env:USERPROFILE\.copilot\mcp-config.json`
- VS Code MCP config: `$env:APPDATA\Code\User\mcp.json`
- Cursor MCP config: `$env:USERPROFILE\.cursor\mcp.json`
- Preferred worktrees: `D:\atlas-worktrees\...`
- Temporary artifacts: `$env:TEMP\atlas-*`

## Bootstrap commands

```powershell
pwsh -File scripts/bootstrap-dev-tooling.ps1 -Check
pwsh -File scripts/bootstrap-dev-tooling.ps1 -DryRun
pwsh -File scripts/bootstrap-dev-tooling.ps1 -Install
```

The script is idempotent: it checks command presence before install attempts and
does not force upgrades.

## Install policy

Preferred order:

1. Existing trusted installation
2. winget user-scope install
3. official installer where winget is unavailable
4. npm (for MCP npm packages)
5. pipx (for Python-based developer tools)

Avoid opaque bootstrap scripts and `curl|iex` patterns.

## Core MCP set for Windows parity

- codebase-memory
- github (runtime `gh auth token` indirection)
- playwright
- context7

Each server must pass startup plus one real tool call in the target client.

## Worktree collision checks (Codebase Memory)

Validate per-worktree key behavior across:

- main checkout path
- at least one alternate worktree path

Do not assume path-equivalent indexes across drive-letter case or junction paths.
If keys collide, require explicit per-worktree project configuration.
