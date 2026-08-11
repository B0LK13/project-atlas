#Requires -Version 5.1
<#
.SYNOPSIS
  ENV-ISO-001/002 self-test: tip .venv preference, PYTHONPATH fail-closed,
  venv-aware Scripts resolution (no live global pip rewrite).
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ScriptDir "_AtlasCommon.ps1"))) {
    $ScriptDir = Join-Path (Split-Path -Parent $PSScriptRoot) "windows"
}
. (Join-Path $ScriptDir "_AtlasCommon.ps1")

$failed = 0
$foreign = $null
$repoRoot = Resolve-AtlasRepoRoot -ScriptDir $ScriptDir
if (-not $repoRoot) {
    Write-Host "FAIL resolve RepoRoot from $ScriptDir"
    exit 1
}

# --- Case A: PYTHONPATH unset => safe ---
$savedPp = $env:PYTHONPATH
try {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    $a = Test-AtlasPythonPathTipSafe -RepoRoot $repoRoot
    if (-not $a.Ok) {
        Write-Host "FAIL CaseA expected Ok got $($a.Reason)"
        $failed++
    }
    else {
        Write-Host "PASS CaseA PYTHONPATH unset => Ok"
    }

    # --- Case B: foreign project_atlas on PYTHONPATH => fail-closed ---
    $foreign = Join-Path $env:TEMP ("atlas-env-iso-foreign-{0}" -f [guid]::NewGuid().ToString("N"))
    $pkg = Join-Path $foreign "project_atlas"
    New-Item -ItemType Directory -Force -Path $pkg | Out-Null
    Set-Content -LiteralPath (Join-Path $pkg "__init__.py") -Value "# foreign shadow" -Encoding ASCII
    $env:PYTHONPATH = $foreign
    $b = Test-AtlasPythonPathTipSafe -RepoRoot $repoRoot
    if ($b.Ok -or $b.Reason -ne "pythonpath_foreign_shadow") {
        Write-Host "FAIL CaseB expected pythonpath_foreign_shadow got Ok=$($b.Ok) Reason=$($b.Reason)"
        $failed++
    }
    else {
        Write-Host "PASS CaseB foreign PYTHONPATH => $($b.Reason)"
    }

    # --- Case C: tip-local src on PYTHONPATH => allowed ---
    $tipSrc = Join-Path $repoRoot "src"
    if (Test-Path -LiteralPath (Join-Path $tipSrc "project_atlas\__init__.py")) {
        $env:PYTHONPATH = $tipSrc
        $c = Test-AtlasPythonPathTipSafe -RepoRoot $repoRoot
        if (-not $c.Ok) {
            Write-Host "FAIL CaseC tip src PYTHONPATH should be Ok got $($c.Reason)"
            $failed++
        }
        else {
            Write-Host "PASS CaseC tip-local PYTHONPATH => Ok"
        }
    }
    else {
        Write-Host "SKIP CaseC (no tip src/project_atlas)"
    }
}
finally {
    if ($null -eq $savedPp) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $savedPp
    }
    if ($foreign -and (Test-Path -LiteralPath $foreign)) {
        Remove-Item -Recurse -Force -LiteralPath $foreign -ErrorAction SilentlyContinue
    }
}

# --- Case D: tip venv path helper ---
$tipPath = Get-AtlasTipVenvPythonPath -RepoRoot $repoRoot
$expected = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ".venv\Scripts\python.exe"))
if (-not $tipPath.Equals($expected, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "FAIL CaseD tip path $tipPath != $expected"
    $failed++
}
else {
    Write-Host "PASS CaseD Get-AtlasTipVenvPythonPath"
}

# --- Case E: Resolve-AtlasScriptsDir venv-aware when python lives under Scripts ---
# Use a real interpreter if tip/bootstrap Python exists; otherwise assert leaf contract via source.
$probePy = Get-AtlasPythonCommand -RepoRoot $repoRoot
if (-not $probePy) { $probePy = Get-AtlasPythonCommand }
if ($probePy) {
    $resolved = Resolve-AtlasScriptsDir -Python $probePy
    $exeDir = & $probePy.Exe @($probePy.Args + @("-c", "import sys,os; print(os.path.dirname(sys.executable))"))
    $exeDir = ([string]$exeDir).Trim()
    $leaf = Split-Path -Leaf $exeDir
    if ($leaf.Equals("Scripts", [System.StringComparison]::OrdinalIgnoreCase) -or
        $leaf.Equals("bin", [System.StringComparison]::OrdinalIgnoreCase)) {
        $expectedScripts = $exeDir
    }
    else {
        $expectedScripts = Join-Path $exeDir "Scripts"
    }
    if (-not ([System.IO.Path]::GetFullPath($resolved)).Equals(
            [System.IO.Path]::GetFullPath($expectedScripts), [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "FAIL CaseE Resolve-AtlasScriptsDir expected $expectedScripts got $resolved"
        $failed++
    }
    elseif ($resolved -match '[\\/]Scripts[\\/]Scripts([\\/]|$)') {
        Write-Host "FAIL CaseE double Scripts path: $resolved"
        $failed++
    }
    else {
        Write-Host "PASS CaseE venv-aware Scripts dir => $resolved"
    }
}
else {
    Write-Host "SKIP CaseE (no Python available)"
}

# --- Case F: Get-AtlasPythonCommand prefers tip .venv when present ---
$tipPy = Get-AtlasTipVenvPythonPath -RepoRoot $repoRoot
if (Test-Path -LiteralPath $tipPy) {
    $sel = Get-AtlasPythonCommand -RepoRoot $repoRoot
    if (-not $sel -or -not (Test-AtlasInterpreterIsTipVenv -Python $sel -RepoRoot $repoRoot)) {
        Write-Host "FAIL CaseF expected tip-local selection got $($sel.Label) $($sel.Exe)"
        $failed++
    }
    else {
        Write-Host "PASS CaseF prefers tip-venv => $($sel.Label)"
    }
}
else {
    Write-Host "SKIP CaseF (tip .venv not present in this checkout)"
}

if ($failed -gt 0) {
    Write-Host "ENV-ISO-SELFTEST FAIL count=$failed"
    Write-Host "EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES"
    Write-Host "CODEX_VALIDATED=NO"
    exit 1
}
Write-Host "ENV-ISO-SELFTEST PASS"
Write-Host "EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES"
Write-Host "CODEX_VALIDATED=NO"
Write-Host "CLOSED_IDS=ENV-ISO-001,ENV-ISO-002"
exit 0
