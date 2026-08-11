#Requires -Version 5.1
<#
.SYNOPSIS
  Stop AS-PROD-INSTALL-001 processes started by atlas-start.ps1.

.DESCRIPTION
  SEC-025: stops tracked processes only after verifying process identity
  (PID + CreationDate + executable + command line + session nonce + parent).
  Mismatch => FAIL CLOSED (no Stop-Process). Never claims RELEASE or PILOT.

.PARAMETER KeepRuntime
  Keep .tmp/productization (vault + logs); only stop processes.
#>
[CmdletBinding()]
param(
    [switch]$KeepRuntime
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ScriptDir = $PSScriptRoot
. (Join-Path $ScriptDir "_AtlasCommon.ps1")

Write-AtlasProductBanner

$repoRoot = Resolve-AtlasRepoRoot -ScriptDir $ScriptDir
if (-not $repoRoot) {
    Write-AtlasProductError `
        -What "Cannot resolve repository root for stop." `
        -Cause "pyproject.toml / apps/web not found relative to scripts/windows." `
        -Action "Run from a Project Atlas checkout." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-stop.ps1"
    exit 1
}

$runtimeRoot = Join-Path $repoRoot ".tmp\productization"
$stateDir = Join-Path $runtimeRoot "state"
$pidFile = Join-Path $stateDir "atlas-pids.json"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "No productization state at $pidFile (nothing tracked to stop)."
    if (-not $KeepRuntime -and (Test-Path -LiteralPath $runtimeRoot)) {
        Write-Host "Removing leftover runtime $runtimeRoot ..."
        Remove-Item -Recurse -Force $runtimeRoot -ErrorAction SilentlyContinue
    }
    Write-Host "PRODUCTIZATION / NOT RELEASE | RELEASE CERTIFIED = NO | PILOT PASS = NO"
    Write-Host "ORPHAN_PROCESS_COUNT=0"
    exit 0
}

try {
    $state = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
}
catch {
    Write-Host "WARN: could not parse $pidFile - $($_.Exception.Message)" -ForegroundColor DarkYellow
    $state = $null
}

$sessionNonce = ""
if ($state -and $state.session_nonce) {
    $sessionNonce = [string]$state.session_nonce
}

$failClosed = 0
$orphan = 0
if ($state -and $state.processes) {
    $summary = Stop-AtlasVerifiedSession -Processes @($state.processes) -SessionNonce $sessionNonce
    $failClosed = [int]$summary.FAIL_CLOSED_COUNT
    $orphan = [int]$summary.ORPHAN_PROCESS_COUNT
}
else {
    Write-Host "State file has no processes array; refusing PID-only kill (SEC-025)." -ForegroundColor Yellow
}

if ($failClosed -gt 0) {
    Write-Host ""
    Write-Host "SEC-025 FAIL CLOSED: $failClosed process(es) not killed due to identity mismatch." -ForegroundColor Red
    Write-Host "ORPHAN_PROCESS_COUNT=$orphan"
    Write-Host "PRODUCTIZATION / NOT RELEASE | RELEASE CERTIFIED = NO | PILOT PASS = NO"
    Write-Host "State file retained at $pidFile for investigation."
    exit 1
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue

if (-not $KeepRuntime -and (Test-Path -LiteralPath $runtimeRoot)) {
    Write-Host "Removing runtime $runtimeRoot ..."
    Remove-Item -Recurse -Force $runtimeRoot -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Stopped productization session." -ForegroundColor Green
Write-Host "ORPHAN_PROCESS_COUNT=$orphan"
Write-Host "PRODUCTIZATION / NOT RELEASE | RELEASE CERTIFIED = NO | PILOT PASS = NO"
if ($orphan -ne 0) {
    exit 1
}
exit 0
