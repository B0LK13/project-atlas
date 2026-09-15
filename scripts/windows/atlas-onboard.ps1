#Requires -Version 5.1
<#
.SYNOPSIS
  AS-PROD-ONBOARD-001 thin Windows first-run orchestrator.

.DESCRIPTION
  PRODUCTIZATION path (NOT RELEASE / NOT PILOT / ALPHA_READY=NO):
  Links stranger install → preflight → start → (future) doctor WITHOUT
  implementing doctor.

  1) Onboard honesty banner
  2) Call existing atlas-preflight.ps1
  3) Call existing atlas-start.ps1 (forwards common start parameters)
  4) Print future-doctor placeholder note (Cloud #254 owns doctor.py)

  Does NOT:
  - call Core doctor CLI (deferred; Cloud #254 owns doctor.py)
  - add Playwright / browser E2E
  - invent authentic estate
  - set ALPHA_READY to YES

  On failure emits structured product errors via shared helper:
    WHAT:   ...
    CAUSE:  ...
    ACTION: ...
    RETRY:  ...

.PARAMETER Vault
  Forwarded to atlas-start.ps1.

.PARAMETER UseDemoFixture
  Forwarded to atlas-start.ps1.

.PARAMETER NonInteractive
  Forwarded to atlas-start.ps1.

.PARAMETER SkipBrowser
  Forwarded to atlas-start.ps1.

.PARAMETER SkipWeb
  Forwarded to atlas-start.ps1.

.PARAMETER SkipInstall
  Forwarded to atlas-start.ps1.

.PARAMETER SkipPreflight
  Skip the explicit onboard preflight step (start still runs its own preflight).

.PARAMETER ApiPort
  Forwarded to atlas-start.ps1 (default 8765).

.PARAMETER WebPort
  Forwarded to atlas-start.ps1 (default 5173).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\atlas-onboard.ps1

.EXAMPLE
  powershell -NoProfile -File scripts\windows\atlas-onboard.ps1 -UseDemoFixture -NonInteractive -SkipBrowser
#>
[CmdletBinding()]
param(
    [string]$Vault = "",
    [switch]$UseDemoFixture,
    [switch]$NonInteractive,
    [switch]$SkipBrowser,
    [switch]$SkipWeb,
    [switch]$SkipInstall,
    [switch]$SkipPreflight,
    [int]$ApiPort = 8765,
    [int]$WebPort = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
. (Join-Path $ScriptDir "_AtlasCommon.ps1")

function Write-AtlasOnboardBanner {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PROJECT ATLAS - FIRST-RUN ONBOARD (AS-PROD-ONBOARD-001)" -ForegroundColor Cyan
    Write-Host "  Chain: install docs → preflight → start → (future) doctor" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  PRODUCTIZATION PATH - NOT RELEASE" -ForegroundColor Yellow
    Write-Host "  NOT RELEASE CERTIFIED" -ForegroundColor Yellow
    Write-Host "  NOT PILOT PASS / PILOT DORMANT_BLOCKED" -ForegroundColor Yellow
    Write-Host "  ALPHA_READY = NO (do not flip from this package)" -ForegroundColor Yellow
    Write-Host "  Doctor CLI: NOT IMPLEMENTED HERE (Cloud #254 / PROD-DOCTOR)" -ForegroundColor Yellow
    Write-Host "  Playwright: intentionally not part of onboard" -ForegroundColor Yellow
    Write-Host "  Orchestrates existing atlas-preflight.ps1 + atlas-start.ps1 only" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

Write-AtlasOnboardBanner
$env:ATLAS_PRODUCTIZATION = "1"
$env:ATLAS_RELEASE_STATUS = "RELEASE CERTIFIED = NO"
$env:ATLAS_PILOT_STATUS = "PILOT = DORMANT_BLOCKED (NOT PILOT PASS)"
$env:ATLAS_ONBOARD_CLAIM = "PRODUCTIZATION / NOT RELEASE / NOT PILOT - first-run link only"
$env:ATLAS_ALPHA_READY = "NO"

$preflight = Join-Path $ScriptDir "atlas-preflight.ps1"
$start = Join-Path $ScriptDir "atlas-start.ps1"

if (-not (Test-Path -LiteralPath $preflight)) {
    Write-AtlasProductError `
        -What "Onboard cannot find atlas-preflight.ps1." `
        -Cause "Expected scripts/windows/atlas-preflight.ps1 next to atlas-onboard.ps1." `
        -Action "Use a full checkout that includes AS-PROD-INSTALL-001 Windows scripts." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-preflight.ps1"
    exit 1
}

if (-not (Test-Path -LiteralPath $start)) {
    Write-AtlasProductError `
        -What "Onboard cannot find atlas-start.ps1." `
        -Cause "Expected scripts/windows/atlas-start.ps1 next to atlas-onboard.ps1." `
        -Action "Use a full checkout that includes AS-PROD-INSTALL-001 Windows scripts." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1"
    exit 1
}

# --- explicit preflight link (install → preflight) ---
if (-not $SkipPreflight) {
    Write-Host "ONBOARD step 1/2: preflight (atlas-preflight.ps1)..." -ForegroundColor Cyan
    & $preflight -SkipBanner
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Onboard stopped: preflight failed." `
            -Cause "scripts/windows/atlas-preflight.ps1 exited with code $LASTEXITCODE." `
            -Action "Resolve printed WHAT/CAUSE/ACTION (Python 3.12+, Node/npm, writable .tmp). See docs/productization/onboard/FIRST-RUN.md." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-onboard.ps1"
        exit 1
    }
}
else {
    Write-Host "ONBOARD: skipping explicit preflight (-SkipPreflight); start still runs its own." -ForegroundColor DarkYellow
}

# --- start link (preflight → start); start re-runs preflight internally ---
Write-Host "ONBOARD step 2/2: start (atlas-start.ps1)..." -ForegroundColor Cyan
$startArgs = @{
    ApiPort = $ApiPort
    WebPort = $WebPort
}
if ($Vault -and $Vault.Trim().Length -gt 0) { $startArgs["Vault"] = $Vault }
if ($UseDemoFixture) { $startArgs["UseDemoFixture"] = $true }
if ($NonInteractive) { $startArgs["NonInteractive"] = $true }
if ($SkipBrowser) { $startArgs["SkipBrowser"] = $true }
if ($SkipWeb) { $startArgs["SkipWeb"] = $true }
if ($SkipInstall) { $startArgs["SkipInstall"] = $true }

& $start @startArgs
$startCode = $LASTEXITCODE
if ($startCode -ne 0) {
    Write-AtlasProductError `
        -What "Onboard stopped: start failed." `
        -Cause "scripts/windows/atlas-start.ps1 exited with code $startCode." `
        -Action "Read WHAT/CAUSE/ACTION from start output and docs/productization/install/STRANGER.md." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-onboard.ps1"
    exit $startCode
}

# --- future doctor slot (do not invoke) ---
Write-Host ""
Write-Host "----------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "  NEXT (future): atlas doctor" -ForegroundColor DarkCyan
Write-Host "  Status: NOT IMPLEMENTED in AS-PROD-ONBOARD-001" -ForegroundColor DarkCyan
Write-Host "  Owner: Cloud #254 / PROD-DOCTOR (doctor.py + CLI wiring)" -ForegroundColor DarkCyan
Write-Host "  This helper does not call doctor and does not use Playwright." -ForegroundColor DarkCyan
Write-Host "  Honesty: PRODUCTIZATION / NOT RELEASE / NOT PILOT / ALPHA_READY=NO" -ForegroundColor DarkCyan
Write-Host "----------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "ONBOARD complete: install → preflight → start linked. Doctor deferred." -ForegroundColor Green
exit 0
