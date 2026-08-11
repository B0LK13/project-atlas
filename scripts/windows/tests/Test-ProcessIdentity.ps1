#Requires -Version 5.1
<#
.SYNOPSIS
  Dual self-test for SEC-025 process identity verify-before-kill (no live kill of foreign procs).
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ScriptDir "_AtlasCommon.ps1"))) {
    $ScriptDir = Join-Path (Split-Path -Parent $PSScriptRoot) "windows"
}
. (Join-Path $ScriptDir "_AtlasCommon.ps1")

$failed = 0

# --- Case A: matching identity => Ok ---
$self = Get-Process -Id $PID
$nonce = New-AtlasSessionNonce
$rec = [pscustomobject]@{
    identity_schema   = "atlas-process-identity/v1"
    name              = "self-test"
    pid               = $PID
    creation_date     = $self.StartTime.ToUniversalTime().ToString("o")
    executable_path   = $self.Path
    command_line      = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").CommandLine
    working_directory = (Get-Location).Path
    session_nonce     = $nonce
    ports             = @()
    parent_pid        = [int](Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
}
$match = Test-AtlasProcessIdentityMatch -Record $rec
if (-not $match.Ok) {
    Write-Host "FAIL CaseA match expected Ok got $($match.Reason): $($match.Detail)"
    $failed++
}
else {
    Write-Host "PASS CaseA identity match for current PowerShell"
}

# --- Case B: creation_date mismatch => fail-closed ---
$bad = $rec.PSObject.Copy()
$bad.creation_date = ([datetime]::UtcNow.AddHours(-5)).ToString("o")
$badMatch = Test-AtlasProcessIdentityMatch -Record $bad
if ($badMatch.Ok) {
    Write-Host "FAIL CaseB expected mismatch"
    $failed++
}
else {
    Write-Host "PASS CaseB creation_date mismatch => $($badMatch.Reason)"
}

# --- Case C: missing session nonce => refuse ---
$legacy = [pscustomobject]@{
    name = "legacy"
    pid  = $PID
}
$leg = Test-AtlasProcessIdentityMatch -Record $legacy
if ($leg.Ok) {
    Write-Host "FAIL CaseC legacy pid-only must refuse"
    $failed++
}
else {
    Write-Host "PASS CaseC legacy refuse => $($leg.Reason)"
}

# --- Case D: loopback assert helper exists ---
$bind = Assert-AtlasLoopbackOnly -Port 1 -Label "probe"
if (-not $bind.ContainsKey("Ok")) {
    Write-Host "FAIL CaseD Assert-AtlasLoopbackOnly shape"
    $failed++
}
else {
    Write-Host "PASS CaseD Assert-AtlasLoopbackOnly Ok=$($bind.Ok)"
}

if ($failed -gt 0) {
    Write-Host "SEC-025-SELFTEST FAIL count=$failed"
    exit 1
}
Write-Host "SEC-025-SELFTEST PASS"
Write-Host "EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES"
Write-Host "CODEX_VALIDATED=NO"
exit 0
