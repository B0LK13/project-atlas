#Requires -Version 5.1
<#
.SYNOPSIS
  AS-DEMO-2.1-001 Windows TECHNICAL DEMO launcher (Mode A / DEMO_FIXTURE).

.DESCRIPTION
  Starts a disposable local demo using DEMO_FIXTURE paths only.
  Prints an honest TECHNICAL DEMO banner and refuses RELEASE CERTIFIED / PILOT PASS claims.
  Pilot remains DORMANT / DORMANT_BLOCKED.

.PARAMETER WithApi
  Also start `atlas live api-serve` against a disposable vault under .tmp/as-demo-2.1-001/
  built only from tests/fixtures/demo/estate (DEMO_FIXTURE). Requires atlas on PATH.

.PARAMETER SkipWeb
  Do not start the Vite web shell (API-only / ops check).

.PARAMETER Port
  Vite dev-server port (default 5173).

.PARAMETER ApiPort
  LIVE_API port when -WithApi (default 8765).
#>
[CmdletBinding()]
param(
    [switch]$WithApi,
    [switch]$SkipWeb,
    [int]$Port = 5173,
    [int]$ApiPort = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-DemoBanner {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PROJECT ATLAS - TECHNICAL DEMO (AS-DEMO-2.1-001)" -ForegroundColor Cyan
    Write-Host "  Mode: DEMO_FIXTURE  |  ATLAS_DEMO_MODE=fixture" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  Certificate target: TECHNICAL DEMO - VERIFIED (when gates pass)" -ForegroundColor Yellow
    Write-Host "  NOT RELEASE CERTIFIED" -ForegroundColor Yellow
    Write-Host "  NOT AUTHENTIC PILOT PASS" -ForegroundColor Yellow
    Write-Host "  DEMO_FIXTURE only (not authentic estate, not release evidence)" -ForegroundColor Yellow
    Write-Host "  PILOT: DORMANT / DORMANT_BLOCKED" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Assert-NoForbiddenClaims {
    param([string[]]$Texts)
    $forbidden = @(
        "RELEASE CERTIFIED = YES",
        "RELEASE CERTIFIED=YES",
        "ESTATE PILOT PASSED",
        "PILOT PASS = YES",
        "PILOT PASS=YES"
    )
    foreach ($t in $Texts) {
        if ([string]::IsNullOrWhiteSpace($t)) { continue }
        foreach ($f in $forbidden) {
            if ($t -like "*$f*") {
                throw "Refusing to launch: env would claim '$f'. Demo launcher never stamps RELEASE CERTIFIED or PILOT PASS."
            }
        }
    }
}

function Test-UnderDemoFixtureAllowlist {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )
    $resolved = [System.IO.Path]::GetFullPath($Candidate)
    $allowed = @(
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "tests\fixtures\demo")),
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "fixtures\demo")),
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "apps\web\public")),
        [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ".tmp\as-demo-2.1-001"))
    )
    foreach ($root in $allowed) {
        if ($resolved.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        $prefix = if ($root.EndsWith("\")) { $root } else { "$root\" }
        if ($resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Resolve-DemoFixtureEstate {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    $candidates = @(
        (Join-Path $RepoRoot "tests\fixtures\demo\estate"),
        (Join-Path $RepoRoot "fixtures\demo\estate")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            return [System.IO.Path]::GetFullPath($c)
        }
    }
    return $null
}

# --- resolve repo root: docs/demo/scripts -> ../../..
$ScriptDir = $PSScriptRoot
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\..\.."))
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
    throw "Cannot resolve repo root from $ScriptDir (expected pyproject.toml under $RepoRoot)."
}

Write-DemoBanner

# Honest status stamps - never YES for release/pilot.
$env:ATLAS_DEMO_MODE = "fixture"
$env:VITE_ATLAS_DEMO_ONLY = "1"
$env:ATLAS_DEMO_CLAIM = "TECHNICAL DEMO - NOT RELEASE CERTIFIED - NOT PILOT PASS - PILOT DORMANT"
$env:ATLAS_RELEASE_STATUS = "RELEASE CERTIFIED = NO"
$env:ATLAS_PILOT_STATUS = "PILOT = DORMANT / DORMANT_BLOCKED (NOT PILOT PASS)"

Assert-NoForbiddenClaims @(
    $env:ATLAS_DEMO_CLAIM,
    $env:ATLAS_RELEASE_STATUS,
    $env:ATLAS_PILOT_STATUS
)

# Refuse Mode B / authentic roots for this Windows DEMO_FIXTURE launcher.
if ($env:AUTHENTIC_ESTATE_ROOT -and $env:AUTHENTIC_ESTATE_ROOT.Trim().Length -gt 0) {
    Write-Host "REFUSED: AUTHENTIC_ESTATE_ROOT is set ($($env:AUTHENTIC_ESTATE_ROOT))." -ForegroundColor Red
    Write-Host "This launcher is DEMO_FIXTURE-only (Mode A). Unset AUTHENTIC_ESTATE_ROOT to continue." -ForegroundColor Red
    exit 1
}
if ($env:ATLAS_DEMO_ROOT -and $env:ATLAS_DEMO_ROOT.Trim().Length -gt 0) {
    if (-not (Test-UnderDemoFixtureAllowlist -Candidate $env:ATLAS_DEMO_ROOT -RepoRoot $RepoRoot)) {
        Write-Host "REFUSED: ATLAS_DEMO_ROOT='$($env:ATLAS_DEMO_ROOT)' is outside DEMO_FIXTURE allowlist." -ForegroundColor Red
        Write-Host "Allowed roots: tests/fixtures/demo, fixtures/demo, apps/web/public, .tmp/as-demo-2.1-001" -ForegroundColor Red
        exit 1
    }
}

$DemoFixtureRoot = Resolve-DemoFixtureEstate -RepoRoot $RepoRoot
$WebPublicRoot = Join-Path $RepoRoot "apps\web\public"
$RuntimeRoot = Join-Path $RepoRoot ".tmp\as-demo-2.1-001"
$StateDir = Join-Path $RuntimeRoot "state"
$VaultDir = Join-Path $RuntimeRoot "vault"
$PidFile = Join-Path $StateDir "demo-pids.json"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if ($DemoFixtureRoot) {
    $env:ATLAS_DEMO_FIXTURE = $DemoFixtureRoot
}

Write-Host "DEMO_FIXTURE root : $(if ($DemoFixtureRoot) { $DemoFixtureRoot } else { '(missing - web stubs only)' })"
Write-Host "Web DEMO stubs    : $WebPublicRoot"
Write-Host "Runtime (tmp)     : $RuntimeRoot"
Write-Host "ATLAS_DEMO_MODE   : $($env:ATLAS_DEMO_MODE)"
Write-Host "VITE_ATLAS_DEMO_ONLY=$($env:VITE_ATLAS_DEMO_ONLY)"
Write-Host "PILOT STATUS      : $($env:ATLAS_PILOT_STATUS)"
Write-Host ""

$fixtureReady = [bool]$DemoFixtureRoot
$webStubReady = (
    (Test-Path (Join-Path $WebPublicRoot "sample-mission-control.json")) -and
    (Test-Path (Join-Path $WebPublicRoot "sample-mission-control.fixture.json"))
)

if (-not $fixtureReady) {
    Write-Host "NOTE: DEMO_FIXTURE estate not present (expected tests/fixtures/demo/estate)." -ForegroundColor DarkYellow
    Write-Host "      Continuing with apps/web/public DEMO/FIXTURE stubs only." -ForegroundColor DarkYellow
}
if (-not $webStubReady) {
    Write-Host "ERROR: required web DEMO stubs missing under apps/web/public." -ForegroundColor Red
    exit 1
}

$processRecords = New-Object System.Collections.Generic.List[object]

function Start-TrackedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )
    $logOut = Join-Path $StateDir "$Name.stdout.log"
    $logErr = Join-Path $StateDir "$Name.stderr.log"
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr
    return [pscustomobject]@{
        name       = $Name
        pid        = $proc.Id
        log_stdout = $logOut
        log_stderr = $logErr
    }
}

# --- optional API against DEMO_FIXTURE-derived disposable vault ---
if ($WithApi) {
    if (-not $fixtureReady) {
        Write-Host "REFUSED -WithApi: tests/fixtures/demo/estate is required for DEMO_FIXTURE vault builds." -ForegroundColor Red
        Write-Host "Omit -WithApi and use web DEMO stubs, or restore the fixture corpus." -ForegroundColor Red
        exit 1
    }
    if (-not (Test-UnderDemoFixtureAllowlist -Candidate $DemoFixtureRoot -RepoRoot $RepoRoot)) {
        throw "Internal error: DEMO_FIXTURE root failed allowlist."
    }
    $atlasCmd = Get-Command atlas -ErrorAction SilentlyContinue
    if (-not $atlasCmd) {
        Write-Host "REFUSED -WithApi: 'atlas' not on PATH. pip install -e `".[dev]`" first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Preparing disposable DEMO vault under $VaultDir (not authentic estate)..."
    if (Test-Path $VaultDir) {
        Remove-Item -Recurse -Force $VaultDir
    }
    & atlas init --output $VaultDir
    if ($LASTEXITCODE -ne 0) { throw "atlas init failed for DEMO vault" }
    $manifest = Join-Path $RuntimeRoot "manifest.json"
    & atlas discover --source $DemoFixtureRoot --output $manifest
    if ($LASTEXITCODE -ne 0) { throw "atlas discover failed against DEMO_FIXTURE" }
    & atlas ingest --manifest $manifest --vault $VaultDir --source $DemoFixtureRoot
    if ($LASTEXITCODE -ne 0) { throw "atlas ingest failed for DEMO vault" }
    & atlas build-indexes --vault $VaultDir
    if ($LASTEXITCODE -ne 0) { throw "atlas build-indexes failed for DEMO vault" }
    & atlas validate --vault $VaultDir
    if ($LASTEXITCODE -ne 0) { throw "atlas validate failed for DEMO vault" }

    Write-Host "Starting LIVE_API against DEMO vault (host loopback only)..."
    $atlasPath = $atlasCmd.Source
    $apiArgs = "live api-serve --vault `"$VaultDir`" --host 127.0.0.1 --port $ApiPort"
    $apiProc = Start-TrackedProcess -Name "live-api" -FilePath $atlasPath `
        -ArgumentList $apiArgs -WorkingDirectory $RepoRoot
    [void]$processRecords.Add($apiProc)
    Write-Host "  LIVE_API (DEMO vault) pid=$($apiProc.pid)  http://127.0.0.1:$ApiPort"
    Write-Host "  NOTE: live_api transport is not authentic pilot; vault is DEMO_FIXTURE-derived." -ForegroundColor DarkYellow
    Write-Host "  PILOT remains DORMANT. RELEASE CERTIFIED = NO." -ForegroundColor DarkYellow
    $env:VITE_ATLAS_API_BASE = "http://127.0.0.1:$ApiPort"
}

# --- web shell in DEMO_ONLY (honest chips / stubs) ---
if (-not $SkipWeb) {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npm) {
        Write-Host "ERROR: npm not found. Install Node.js to run apps/web." -ForegroundColor Red
        exit 1
    }
    $webDir = Join-Path $RepoRoot "apps\web"
    if (-not (Test-Path (Join-Path $webDir "package.json"))) {
        throw "apps/web/package.json missing"
    }
    if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
        Write-Host "Installing apps/web dependencies (npm install)..."
        Push-Location $webDir
        try {
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        }
        finally { Pop-Location }
    }
    Write-Host "Starting Vite web shell with VITE_ATLAS_DEMO_ONLY=1 ..."
    # Child inherits ATLAS_DEMO_MODE / VITE_ATLAS_DEMO_ONLY from this process.
    $webArgs = "run dev -- --host 127.0.0.1 --port $Port"
    $webProc = Start-TrackedProcess -Name "web-demo" -FilePath $npm.Source `
        -ArgumentList $webArgs -WorkingDirectory $webDir
    [void]$processRecords.Add($webProc)
    Write-Host "  Web DEMO pid=$($webProc.pid)"
    Write-Host "  Open: http://127.0.0.1:$Port/#/mission-control?mode=demo"
    Write-Host "        http://127.0.0.1:$Port/#/workspace?mode=fixture"
}

$started = [ordered]@{
    package             = "AS-DEMO-2.1-001"
    mode                = "DEMO_FIXTURE"
    release_certified   = $false
    pilot_pass          = $false
    pilot_status        = "DORMANT"
    note                = "TECHNICAL DEMO session - NOT RELEASE CERTIFIED - NOT AUTHENTIC PILOT PASS - PILOT DORMANT"
    demo_fixture_root   = $DemoFixtureRoot
    web_public_root     = $WebPublicRoot
    runtime_root        = $RuntimeRoot
    processes           = @($processRecords.ToArray())
}
$started | ConvertTo-Json -Depth 6 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ""
Write-Host "State written: $PidFile"
Write-Host "Stop with:  powershell -File docs\demo\scripts\demo-down.ps1"
Write-Host ""
Write-Host "HONEST STATUS:" -ForegroundColor Yellow
Write-Host "  TECHNICAL DEMO launcher running (DEMO_FIXTURE paths only)" -ForegroundColor Yellow
Write-Host "  RELEASE CERTIFIED = NO" -ForegroundColor Yellow
Write-Host "  AUTHENTIC PILOT PASS = NO" -ForegroundColor Yellow
Write-Host "  PILOT = DORMANT" -ForegroundColor Yellow
Write-Host "  Demo success is not v2.1.0 release certification" -ForegroundColor Yellow
Write-Host ""
exit 0