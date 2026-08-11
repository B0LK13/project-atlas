# OPERATOR guide — productization install

> **PRODUCTIZATION / NOT RELEASE / NOT PILOT**
> For operators running the Windows stranger bootstrap with explicit vault choices.

## Scripts

| Script | Role |
|---|---|
| `scripts/windows/atlas-preflight.ps1` | Reusable checks (Python 3.12+, Node/npm, repo, writable `.tmp`) |
| `scripts/windows/atlas-start.ps1` | One-action start: preflight → install → vault → API → web → health → browser |
| `scripts/windows/atlas-stop.ps1` | Stop tracked PIDs under `.tmp/productization/state` |
| `scripts/windows/_AtlasCommon.ps1` | Shared helpers (banner, product errors, health waits) |

## Vault modes

1. **DEMO_FIXTURE (default when present)**  
   Builds a disposable vault under `.tmp/productization/vault` from:
   - `tests/fixtures/demo/estate`, or
   - `fixtures/demo/estate`  
   Force with `-UseDemoFixture`.

2. **Operator vault (`-Vault`)**  
   Use an **existing** vault directory. The launcher does not invent authentic estate roots from `AUTHENTIC_ESTATE_ROOT`.

3. **Interactive prompt**  
   When fixtures are missing and `-NonInteractive` is not set, the script asks for an existing vault path.

## Useful flags

```powershell
# Disposable DEMO_FIXTURE path, no prompts, no browser
powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture -NonInteractive -SkipBrowser

# Existing vault
powershell -NoProfile -File scripts\windows\atlas-start.ps1 -Vault D:\path\to\vault

# API only
powershell -NoProfile -File scripts\windows\atlas-start.ps1 -SkipWeb -UseDemoFixture -NonInteractive

# Alternate ports (still 127.0.0.1)
powershell -NoProfile -File scripts\windows\atlas-start.ps1 -ApiPort 8765 -WebPort 5173
```

## Health

- API: `http://127.0.0.1:<ApiPort>/v1/meta`
- Web: TCP/HTTP on `http://127.0.0.1:<WebPort>/`
- State: `.tmp/productization/state/atlas-pids.json`
- Errors: `.tmp/productization/logs/*-errors.log` with WHAT / CAUSE / ACTION / RETRY

## Limitations

See [LIMITATIONS.md](./LIMITATIONS.md). This path does not ship MSI/winget/signing and must not be labeled RELEASE or PILOT PASS.

## SEC-009 Web ↔ LIVE_API credential (local-only)

tlas-start.ps1 captures the per-launch ATLAS_API_READ_TOKEN printed by
tlas live api-serve on stderr and propagates it to the Vite process as
VITE_ATLAS_API_TOKEN (READ scope only). The token is local to that launch —
not committed, not placed in URLs, and not a privileged credential. Auth stays
required; do not disable SEC-009 for demos.
