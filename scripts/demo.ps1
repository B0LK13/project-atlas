<#
.SYNOPSIS
  Project Atlas Technical Demo outline (Windows-first) - AS-DEMO-2.1-001

.DESCRIPTION
  Scaffold / operator outline for Mode A (DEMO_FIXTURE).

  Banner (always):
    DEMO · NOT AUTHENTIC PILOT · NOT RELEASE EVIDENCE

  This script does NOT:
    - invent .atlas-project.yaml in real projects
    - claim authentic estate pilot success
    - claim v2.1.0 release certification
    - invent API routes that do not exist on the current tip

.PARAMETER Help
  Print usage and exit 0.

.PARAMETER InitVault
  Run atlas init → discover → ingest → build-indexes → validate against
  tests/fixtures/demo into .tmp/demo-vault.

.PARAMETER SmokeApi
  GET a small set of local health/project routes (best-effort; skips missing).

.PARAMETER ApiBase
  Base URL for SmokeApi (default http://127.0.0.1:8765).

.PARAMETER Vault
  Vault path (default .tmp/demo-vault under repo root).

.EXAMPLE
  .\scripts\demo.ps1 -Help
  .\scripts\demo.ps1 -InitVault
  .\scripts\demo.ps1 -SmokeApi
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [switch]$InitVault,
    [switch]$SmokeApi,
    [string]$ApiBase = "http://127.0.0.1:8765",
    [string]$Vault = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-DemoBanner {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host " DEMO - NOT AUTHENTIC PILOT - NOT RELEASE EVIDENCE" -ForegroundColor Yellow
    Write-Host " AS-DEMO-2.1-001 TECHNICAL_PREVIEW (Mode A fixture)" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
}

function Get-RepoRoot {
    $here = $PSScriptRoot
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    return (Resolve-Path (Join-Path $here "..")).Path
}

function Show-Help {
    Write-DemoBanner
    @"
Usage:
  .\scripts\demo.ps1 -Help
  .\scripts\demo.ps1 -InitVault [-Vault <.tmp\demo-vault>]
  .\scripts\demo.ps1 -SmokeApi [-ApiBase http://127.0.0.1:8765]

DEMO_FIXTURE (normative discover root):
  tests\fixtures\demo\estate\

Mode A env (set by -InitVault):
  ATLAS_DEMO_MODE=fixture
  ATLAS_DEMO_FIXTURE=<absolute tests\fixtures\demo\estate>

Next steps after -InitVault (manual / separate terminals):
  1) atlas live api-serve --vault <Vault> --host 127.0.0.1 --port 8765
  2) cd apps\web; `$env:VITE_ATLAS_DEMO_ONLY='1'; npm run dev
  3) Follow docs\demo\DEMO-SCRIPT.md

Forbidden:
  Creating .atlas-project.yaml in real projects to fake authentic pilot.
"@ | Write-Host
}

function Assert-AtlasOnPath {
    $cmd = Get-Command atlas -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "atlas CLI not found on PATH. Activate .venv and pip install -e `".[dev]`" first (see docs/demo/QUICKSTART.md)."
    }
}

function Invoke-InitVault {
    param([string]$RepoRoot, [string]$VaultPath)

    Assert-AtlasOnPath

    $fixture = Join-Path $RepoRoot "tests\fixtures\demo\estate"
    if (-not (Test-Path -LiteralPath $fixture)) {
        throw "DEMO_FIXTURE missing: $fixture"
    }

    $tmp = Join-Path $RepoRoot ".tmp"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null

    $manifest = Join-Path $tmp "demo-manifest.json"

    Write-Host "DEMO_FIXTURE: $fixture"
    Write-Host "Vault:        $VaultPath"
    Write-Host "Manifest:     $manifest"

    $env:ATLAS_DEMO_MODE = "fixture"
    $env:ATLAS_DEMO_FIXTURE = (Resolve-Path -LiteralPath $fixture).Path
    # Explicitly do not set AUTHENTIC_ESTATE_ROOT from this corpus.
    if (Test-Path Env:AUTHENTIC_ESTATE_ROOT) {
        Remove-Item Env:AUTHENTIC_ESTATE_ROOT
    }

    if (Test-Path -LiteralPath $VaultPath) {
        Write-Host "Removing prior demo vault (disposable): $VaultPath"
        Remove-Item -LiteralPath $VaultPath -Recurse -Force
    }

    atlas init --output $VaultPath
    if ($LASTEXITCODE -ne 0) { throw "atlas init failed ($LASTEXITCODE)" }

    atlas discover --source $fixture --output $manifest
    if ($LASTEXITCODE -ne 0) { throw "atlas discover failed ($LASTEXITCODE)" }

    atlas ingest --manifest $manifest --vault $VaultPath --source $fixture
    if ($LASTEXITCODE -ne 0) { throw "atlas ingest failed ($LASTEXITCODE)" }

    atlas build-indexes --vault $VaultPath
    if ($LASTEXITCODE -ne 0) { throw "atlas build-indexes failed ($LASTEXITCODE)" }

    atlas validate --vault $VaultPath
    if ($LASTEXITCODE -ne 0) { throw "atlas validate failed ($LASTEXITCODE)" }

    Write-Host ""
    Write-Host "InitVault complete. Still: DEMO - NOT AUTHENTIC PILOT - NOT RELEASE EVIDENCE"
    Write-Host "Next: atlas live api-serve --vault `"$VaultPath`" --host 127.0.0.1 --port 8765"
}

function Invoke-SmokeApi {
    param([string]$Base)

    $paths = @(
        "/health",
        "/v1/health",
        "/v1/projects"
    )

    foreach ($p in $paths) {
        $url = ($Base.TrimEnd("/") + $p)
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            Write-Host ("OK  {0} -> {1}" -f $url, [int]$resp.StatusCode)
        }
        catch {
            Write-Host ("SKIP/FAIL {0} -> {1}" -f $url, $_.Exception.Message) -ForegroundColor DarkYellow
        }
    }

    Write-Host "SmokeApi finished (best-effort). Do not invent missing routes for demo optics."
}

# --- main ---
Write-DemoBanner

if ($Help -or (-not $InitVault -and -not $SmokeApi)) {
    Show-Help
    if (-not $Help -and -not $InitVault -and -not $SmokeApi) {
        exit 0
    }
    if ($Help) { exit 0 }
}

$repoRoot = Get-RepoRoot
if ([string]::IsNullOrWhiteSpace($Vault)) {
    $Vault = Join-Path $repoRoot ".tmp\demo-vault"
}

if ($InitVault) {
    Invoke-InitVault -RepoRoot $repoRoot -VaultPath $Vault
}

if ($SmokeApi) {
    Invoke-SmokeApi -Base $ApiBase
}

exit 0
