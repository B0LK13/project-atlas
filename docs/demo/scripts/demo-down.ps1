#Requires -Version 5.1
<#
.SYNOPSIS
  Tear down AS-DEMO-2.1-001 Windows TECHNICAL DEMO processes started by demo-up.ps1.

.DESCRIPTION
  Stops tracked PIDs under .tmp/as-demo-2.1-001/state and optionally removes the
  disposable DEMO runtime directory. Never claims RELEASE CERTIFIED or PILOT PASS.
  Pilot remains DORMANT.

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
    exit 0
}

try {
    $state = Get-Content -Raw -Path $PidFile | ConvertFrom-Json
}
catch {
    Write-Host "WARN: could not parse $PidFile - $($_.Exception.Message)" -ForegroundColor DarkYellow
    $state = $null
}

if ($state -and $state.processes) {
    foreach ($procInfo in @($state.processes)) {
        $procId = [int]$procInfo.pid
        $name = [string]$procInfo.name
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "Stopping $name pid=$procId ($($p.ProcessName))..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            # Also stop child cmd/npm trees when present
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
                ForEach-Object {
                    Write-Host "  stopping child pid=$($_.ProcessId) $($_.Name)"
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                }
        }
        catch {
            Write-Host "  pid=$procId already gone ($name)"
        }
    }
}

Remove-Item -Force $PidFile -ErrorAction SilentlyContinue

if (-not $KeepRuntime) {
    if (Test-Path $RuntimeRoot) {
        Write-Host "Removing disposable DEMO runtime $RuntimeRoot ..."
        Start-Sleep -Milliseconds 300
        Remove-Item -Recurse -Force $RuntimeRoot -ErrorAction SilentlyContinue
    }
}
else {
    Write-Host "Kept runtime at $RuntimeRoot (-KeepRuntime)."
}

Write-Host ""
Write-Host "Teardown complete."
Write-Host "HONEST STATUS: TECHNICAL DEMO stopped | RELEASE CERTIFIED = NO | PILOT PASS = NO | PILOT DORMANT" -ForegroundColor Yellow
Write-Host ""
exit 0