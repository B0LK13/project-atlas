#Requires -Version 5.1
<#
.SYNOPSIS
  Stop AS-PROD-INSTALL-001 processes started by atlas-start.ps1.

.DESCRIPTION
  Stops tracked PIDs under .tmp/productization/state. Never claims RELEASE or PILOT.
  Optional cleanup of disposable runtime (keeps honesty: PRODUCTIZATION / NOT RELEASE).

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
    exit 0
}

try {
    $state = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
}
catch {
    Write-Host "WARN: could not parse $pidFile - $($_.Exception.Message)" -ForegroundColor DarkYellow
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

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue

if (-not $KeepRuntime -and (Test-Path -LiteralPath $runtimeRoot)) {
    Write-Host "Removing runtime $runtimeRoot ..."
    Remove-Item -Recurse -Force $runtimeRoot -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Stopped productization session." -ForegroundColor Green
Write-Host "PRODUCTIZATION / NOT RELEASE | RELEASE CERTIFIED = NO | PILOT PASS = NO"
exit 0
