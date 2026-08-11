#Requires -Version 5.1
<#
.SYNOPSIS
  Tear down AS-DEMO-2.1-001 Windows TECHNICAL DEMO processes started by demo-up.ps1.

.DESCRIPTION
  SEC-025 / SEC-ADV004-A-004: stops tracked processes only after verifying process
  identity via scripts/windows/_AtlasCommon.ps1 (same gate as atlas-stop.ps1).
  Never claims RELEASE CERTIFIED or PILOT PASS. Pilot remains DORMANT.

.PARAMETER KeepRuntime
  Keep .tmp/as-demo-2.1-001 (vault + logs); only stop processes.
#>
[CmdletBinding()]
param(
    [switch]$KeepRuntime
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Write-DemoBanner {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PROJECT ATLAS - TECHNICAL DEMO TEARDOWN (AS-DEMO-2.1-001)" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  NOT RELEASE CERTIFIED" -ForegroundColor Yellow
    Write-Host "  NOT AUTHENTIC PILOT PASS" -ForegroundColor Yellow
    Write-Host "  DEMO_FIXTURE session end is not estate pilot closeout" -ForegroundColor Yellow
    Write-Host "  PILOT remains DORMANT" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

$ScriptDir = $PSScriptRoot
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\..\.."))
$Common = Join-Path $RepoRoot "scripts\windows\_AtlasCommon.ps1"
if (-not (Test-Path -LiteralPath $Common)) {
    Write-Host "FAIL: missing $Common (cannot verify-before-kill)." -ForegroundColor Red
    exit 1
}
. $Common

$RuntimeRoot = Join-Path $RepoRoot ".tmp\as-demo-2.1-001"
$StateDir = Join-Path $RuntimeRoot "state"
$PidFile = Join-Path $StateDir "demo-pids.json"

Write-DemoBanner

if (-not (Test-Path $PidFile)) {
    Write-Host "No demo state at $PidFile (nothing tracked to stop)."
    if (-not $KeepRuntime -and (Test-Path $RuntimeRoot)) {
        Write-Host "Removing leftover runtime $RuntimeRoot ..."
        Remove-Item -Recurse -Force $RuntimeRoot -ErrorAction SilentlyContinue
    }
    Write-Host "RELEASE CERTIFIED = NO | PILOT PASS = NO | PILOT DORMANT"
    Write-Host "ORPHAN_PROCESS_COUNT=0"
    exit 0
}

try {
    $state = Get-Content -Raw -Path $PidFile | ConvertFrom-Json
}
catch {
    Write-Host "WARN: could not parse $PidFile - $($_.Exception.Message)" -ForegroundColor DarkYellow
    $state = $null
}

$sessionNonce = ""
if ($state -and $state.PSObject.Properties["session_nonce"]) {
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
    Write-Host "RELEASE CERTIFIED = NO | PILOT PASS = NO | PILOT DORMANT"
    Write-Host "State file retained at $PidFile for investigation."
    exit 1
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue

if (-not $KeepRuntime -and (Test-Path $RuntimeRoot)) {
    Write-Host "Removing runtime $RuntimeRoot ..."
    Remove-Item -Recurse -Force $RuntimeRoot -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Stopped DEMO session." -ForegroundColor Green
Write-Host "ORPHAN_PROCESS_COUNT=$orphan"
Write-Host "RELEASE CERTIFIED = NO | PILOT PASS = NO | PILOT DORMANT"
if ($orphan -ne 0) {
    exit 1
}
exit 0
