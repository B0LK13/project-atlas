#Requires -Version 5.1
<#
.SYNOPSIS
  AS-PROD-INSTALL-001 one-action Windows stranger bootstrap (start Atlas locally).

.DESCRIPTION
  PRODUCTIZATION path (NOT RELEASE / NOT PILOT):
  1) honesty banner
  2) preflight (Python 3.12+, Node/npm, repo root, writable .tmp)
  3) editable Core install if needed (pip install -e ".[dev]")
  4) configure vault: DEMO_FIXTURE bootstrap under .tmp/productization OR operator vault path
  5) start atlas live api-serve on 127.0.0.1 (bounded)
  6) start apps/web (npm run dev) without Playwright
  7) health checks (API /v1/meta + web port)
  8) open local Atlas URL in the default browser

  Never invents authentic estate. Prefer DEMO_FIXTURE + .tmp/productization.
  On failure: structured product errors to stderr + log:
    WHAT:   ...
    CAUSE:  ...
    ACTION: ...
    RETRY:  ...

.PARAMETER Vault
  Existing vault directory. When omitted, uses DEMO_FIXTURE bootstrap when available,
  otherwise prompts (unless -NonInteractive).

.PARAMETER UseDemoFixture
  Force disposable vault build from DEMO_FIXTURE estate paths.

.PARAMETER NonInteractive
  Fail closed instead of prompting for a vault path.

.PARAMETER SkipBrowser
  Do not open the default browser after health checks.

.PARAMETER SkipWeb
  Start API only (still PRODUCTIZATION / NOT RELEASE).

.PARAMETER SkipInstall
  Skip pip install -e ".[dev]" even if atlas is missing (advanced).

.PARAMETER ApiPort
  LIVE_API port (default 8765). Bound to 127.0.0.1 only.

.PARAMETER WebPort
  Vite web port (default 5173).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\atlas-start.ps1

.EXAMPLE
  powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture -NonInteractive
#>
[CmdletBinding()]
param(
    [string]$Vault = "",
    [switch]$UseDemoFixture,
    [switch]$NonInteractive,
    [switch]$SkipBrowser,
    [switch]$SkipWeb,
    [switch]$SkipInstall,
    [int]$ApiPort = 8765,
    [int]$WebPort = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
. (Join-Path $ScriptDir "_AtlasCommon.ps1")

function Start-TrackedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$StateDir
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

function Ensure-AtlasEditableInstall {
    param(
        [Parameter(Mandatory = $true)]$Python,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$ErrLog,
        [switch]$SkipInstall
    )
    $atlasCmd = Get-Command atlas -ErrorAction SilentlyContinue
    if ($atlasCmd) {
        Write-Host "OK  atlas on PATH: $($atlasCmd.Source)"
        return $atlasCmd.Source
    }
    if ($SkipInstall) {
        Write-AtlasProductError `
            -What "Atlas CLI ('atlas') is not on PATH." `
            -Cause "-SkipInstall was set and no atlas console script was found." `
            -Action "Remove -SkipInstall or run: pip install -e `".[dev]`" from the repo root, then reopen the shell." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $ErrLog
        exit 1
    }
    Write-Host "Configuring: editable install pip install -e `".[dev]`" ..."
    $code = Invoke-AtlasPython -Python $Python -WorkingDirectory $RepoRoot -Arguments @(
        "-m", "pip", "install", "-e", ".[dev]"
    )
    if ($code -ne 0) {
        Write-AtlasProductError `
            -What "Editable install of Project Atlas failed." `
            -Cause "pip install -e `".[dev]`" exited with code $code." `
            -Action "Ensure Python 3.12+ and pip work, then from repo root run: python -m pip install -e `".[dev]`". Check network/proxy if packages cannot download." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $ErrLog
        exit 1
    }
    $atlasCmd = Get-Command atlas -ErrorAction SilentlyContinue
    if (-not $atlasCmd) {
        # Prefer Scripts next to the interpreter when PATH was not refreshed.
        $hint = Join-Path (Split-Path $Python.Exe -Parent) "Scripts\atlas.exe"
        if (Test-Path -LiteralPath $hint) {
            Write-Host "OK  atlas at $hint (PATH not refreshed; using absolute path)"
            return $hint
        }
        Write-AtlasProductError `
            -What "Install finished but 'atlas' is still not discoverable." `
            -Cause "pip reported success but no atlas.exe was found on PATH or beside the Python Scripts directory." `
            -Action "Close and reopen PowerShell so PATH updates, or add Python Scripts to PATH. Confirm: python -m pip show project-atlas" `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $ErrLog
        exit 1
    }
    Write-Host "OK  atlas installed: $($atlasCmd.Source)"
    return $atlasCmd.Source
}

function Build-DemoFixtureVault {
    param(
        [Parameter(Mandatory = $true)][string]$AtlasExe,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$VaultDir,
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$FixtureRoot,
        [Parameter(Mandatory = $true)][string]$ErrLog
    )
    Write-Host "Bootstrapping disposable vault from DEMO_FIXTURE (not authentic estate)..."
    Write-Host "  fixture: $FixtureRoot"
    Write-Host "  vault:   $VaultDir"
    if (Test-Path -LiteralPath $VaultDir) {
        Remove-Item -Recurse -Force $VaultDir
    }
    & $AtlasExe init --output $VaultDir
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Failed to initialize disposable productization vault." `
            -Cause "atlas init exited with code $LASTEXITCODE." `
            -Action "Inspect Core install (atlas version). Ensure VaultDir under .tmp/productization is empty/writable." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture" `
            -LogPath $ErrLog
        exit 1
    }
    $manifest = Join-Path $RuntimeRoot "manifest.json"
    & $AtlasExe discover --source $FixtureRoot --output $manifest
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Failed to discover DEMO_FIXTURE sources." `
            -Cause "atlas discover exited with code $LASTEXITCODE against $FixtureRoot." `
            -Action "Confirm fixtures exist under tests/fixtures/demo/estate or fixtures/demo/estate." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture" `
            -LogPath $ErrLog
        exit 1
    }
    & $AtlasExe ingest --manifest $manifest --vault $VaultDir
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Failed to ingest DEMO_FIXTURE into disposable vault." `
            -Cause "atlas ingest exited with code $LASTEXITCODE." `
            -Action "Read ingest logs; fix fixture corpus; do not substitute authentic estate without an explicit operator vault path." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture" `
            -LogPath $ErrLog
        exit 1
    }
    & $AtlasExe build-indexes --vault $VaultDir
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Failed to build indexes for disposable vault." `
            -Cause "atlas build-indexes exited with code $LASTEXITCODE." `
            -Action "Re-run after a clean .tmp/productization/vault or report Core index errors." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture" `
            -LogPath $ErrLog
        exit 1
    }
    & $AtlasExe validate --vault $VaultDir
    if ($LASTEXITCODE -ne 0) {
        Write-AtlasProductError `
            -What "Disposable vault failed validation." `
            -Cause "atlas validate exited with code $LASTEXITCODE." `
            -Action "Treat as a Core/fixture issue. Do not claim STRANGER_CAN_START_ATLAS until validate passes." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture" `
            -LogPath $ErrLog
        exit 1
    }
    Write-Host "OK  DEMO_FIXTURE disposable vault ready (PRODUCTIZATION only)"
}

function Ensure-WebDependencies {
    param(
        [Parameter(Mandatory = $true)]$Npm,
        [Parameter(Mandatory = $true)][string]$WebDir,
        [Parameter(Mandatory = $true)][string]$ErrLog
    )
    $modules = Join-Path $WebDir "node_modules"
    $rollupNative = Join-Path $modules "@rollup\rollup-win32-x64-msvc"
    $needsInstall = -not (Test-Path -LiteralPath $modules)
    $needsRepair = (Test-Path -LiteralPath $modules) -and -not (Test-Path -LiteralPath $rollupNative)

    if ($needsRepair) {
        Write-Host "Repairing apps/web node_modules (missing Rollup Windows optional native)..."
        Remove-Item -Recurse -Force $modules -ErrorAction SilentlyContinue
        $needsInstall = $true
    }

    if ($needsInstall) {
        Write-Host "Installing apps/web dependencies (npm install; no Playwright)..."
        Push-Location $WebDir
        try {
            & $Npm.Source install --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) {
                Write-AtlasProductError `
                    -What "npm install for apps/web failed." `
                    -Cause "npm install exited with code $LASTEXITCODE." `
                    -Action "Check network/proxy and Node version. Do not add Playwright packages for this productization path." `
                    -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
                    -LogPath $ErrLog
                exit 1
            }
            # npm optional-deps bug on Windows can omit @rollup/rollup-win32-x64-msvc.
            if (-not (Test-Path -LiteralPath $rollupNative)) {
                Write-Host "Installing Rollup Windows native optional dependency..."
                & $Npm.Source install --no-fund --no-audit --include=optional "@rollup/rollup-win32-x64-msvc"
                if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $rollupNative)) {
                    Write-AtlasProductError `
                        -What "apps/web install is missing the Windows Rollup native module." `
                        -Cause "Optional dependency @rollup/rollup-win32-x64-msvc was not present after npm install (known npm optional-deps issue)." `
                        -Action "From apps/web run: Remove-Item -Recurse -Force node_modules; npm install --include=optional. Do not add Playwright." `
                        -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
                        -LogPath $ErrLog
                    exit 1
                }
            }
        }
        finally { Pop-Location }
    }
}

# --- banner + honesty stamps ---
Write-AtlasProductBanner
$env:ATLAS_PRODUCTIZATION = "1"
$env:ATLAS_RELEASE_STATUS = "RELEASE CERTIFIED = NO"
$env:ATLAS_PILOT_STATUS = "PILOT = DORMANT_BLOCKED (NOT PILOT PASS)"
$env:ATLAS_INSTALL_CLAIM = "PRODUCTIZATION / NOT RELEASE / NOT PILOT - STRANGER_CAN_START_ATLAS local path"

$repoRoot = Resolve-AtlasRepoRoot -ScriptDir $ScriptDir
if (-not $repoRoot) {
    Write-AtlasProductError `
        -What "Cannot resolve Project Atlas repository root." `
        -Cause "scripts/windows helpers could not find pyproject.toml + apps/web." `
        -Action "Run from a full git checkout of B0LK13/project-atlas." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1"
    exit 1
}

$runtimeRoot = Join-Path $repoRoot ".tmp\productization"
$stateDir = Join-Path $runtimeRoot "state"
$logDir = Join-Path $runtimeRoot "logs"
$errLog = Join-Path $logDir "start-errors.log"
$pidFile = Join-Path $stateDir "atlas-pids.json"
$defaultVault = Join-Path $runtimeRoot "vault"
New-Item -ItemType Directory -Force -Path $stateDir, $logDir | Out-Null

# Refuse inventing authentic estate via env
if ($env:AUTHENTIC_ESTATE_ROOT -and $env:AUTHENTIC_ESTATE_ROOT.Trim().Length -gt 0 -and -not $Vault) {
    Write-Host "NOTE: AUTHENTIC_ESTATE_ROOT is set but this launcher will not invent estate from it." -ForegroundColor DarkYellow
    Write-Host "      Pass -Vault <existing-vault> explicitly if you already have an operator vault." -ForegroundColor DarkYellow
}

# --- preflight (reusable) ---
Write-Host "Running preflight..."
& (Join-Path $ScriptDir "atlas-preflight.ps1") -SkipBanner
if ($LASTEXITCODE -ne 0) {
    Write-AtlasProductError `
        -What "Preflight failed; Atlas was not started." `
        -Cause "scripts/windows/atlas-preflight.ps1 exited with code $LASTEXITCODE." `
        -Action "Resolve the printed WHAT/CAUSE/ACTION items (Python 3.12+, Node/npm, writable .tmp)." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-preflight.ps1" `
        -LogPath $errLog
    exit 1
}

$python = Get-AtlasPythonCommand
if (-not $python) {
    Write-AtlasProductError `
        -What "Python 3.12+ disappeared after preflight." `
        -Cause "Get-AtlasPythonCommand returned null unexpectedly." `
        -Action "Re-run preflight and confirm Python remains on PATH." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
        -LogPath $errLog
    exit 1
}

$atlasExe = Ensure-AtlasEditableInstall -Python $python -RepoRoot $repoRoot -ErrLog $errLog -SkipInstall:$SkipInstall

# --- vault configure ---
$fixtureRoot = Resolve-DemoFixtureEstate -RepoRoot $repoRoot
$vaultPath = $null
$vaultMode = $null

if ($Vault -and $Vault.Trim().Length -gt 0) {
    $vaultPath = [System.IO.Path]::GetFullPath($Vault)
    if (-not (Test-Path -LiteralPath $vaultPath)) {
        Write-AtlasProductError `
            -What "Operator vault path does not exist." `
            -Cause "Path '$vaultPath' was not found." `
            -Action "Pass an existing vault directory, or omit -Vault to use DEMO_FIXTURE under .tmp/productization." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -Vault <path>" `
            -LogPath $errLog
        exit 1
    }
    $vaultMode = "operator_vault"
}
elseif ($UseDemoFixture -or $fixtureRoot) {
    if (-not $fixtureRoot) {
        Write-AtlasProductError `
            -What "DEMO_FIXTURE estate is missing." `
            -Cause "Expected tests/fixtures/demo/estate or fixtures/demo/estate." `
            -Action "Restore DEMO_FIXTURE corpus, or pass -Vault <existing-vault>. This launcher will not invent authentic estate." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -Vault <path>" `
            -LogPath $errLog
        exit 1
    }
    Build-DemoFixtureVault -AtlasExe $atlasExe -RepoRoot $repoRoot -VaultDir $defaultVault `
        -RuntimeRoot $runtimeRoot -FixtureRoot $fixtureRoot -ErrLog $errLog
    $vaultPath = $defaultVault
    $vaultMode = "demo_fixture"
}
else {
    if ($NonInteractive) {
        Write-AtlasProductError `
            -What "No vault configured in non-interactive mode." `
            -Cause "DEMO_FIXTURE estate was not found and -Vault was not provided." `
            -Action "Provide -Vault <path> or restore DEMO_FIXTURE, then pass -UseDemoFixture." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -UseDemoFixture -NonInteractive" `
            -LogPath $errLog
        exit 1
    }
    Write-Host ""
    Write-Host "No DEMO_FIXTURE estate found. Enter an EXISTING vault path." -ForegroundColor Yellow
    Write-Host "Do not invent authentic estate roots. Prefer a disposable vault under .tmp/productization." -ForegroundColor Yellow
    $inputVault = Read-Host "Vault path (or blank to cancel)"
    if ([string]::IsNullOrWhiteSpace($inputVault)) {
        Write-AtlasProductError `
            -What "Start cancelled: no vault path provided." `
            -Cause "Operator declined vault prompt and DEMO_FIXTURE was unavailable." `
            -Action "Create/init a vault or restore DEMO_FIXTURE, then retry." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -Vault <path>" `
            -LogPath $errLog
        exit 1
    }
    $vaultPath = [System.IO.Path]::GetFullPath($inputVault)
    if (-not (Test-Path -LiteralPath $vaultPath)) {
        Write-AtlasProductError `
            -What "Entered vault path does not exist." `
            -Cause "Path '$vaultPath' was not found." `
            -Action "Init a vault with 'atlas init --output <dir>' or restore DEMO_FIXTURE." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1 -Vault <path>" `
            -LogPath $errLog
        exit 1
    }
    $vaultMode = "operator_prompt"
}

Write-Host "Vault mode : $vaultMode"
Write-Host "Vault path : $vaultPath"
Write-Host "Runtime    : $runtimeRoot"
Write-Host ""

$processRecords = New-Object System.Collections.Generic.List[object]

# --- start LIVE_API (loopback only) ---
Write-Host "Starting LIVE_API on 127.0.0.1:$ApiPort ..."
$apiArgs = "live api-serve --vault `"$vaultPath`" --host 127.0.0.1 --port $ApiPort"
$apiProc = Start-TrackedProcess -Name "live-api" -FilePath $atlasExe `
    -ArgumentList $apiArgs -WorkingDirectory $repoRoot -StateDir $stateDir
[void]$processRecords.Add($apiProc)
Write-Host "  LIVE_API pid=$($apiProc.pid)"

$apiHealth = Wait-AtlasHttpOk -Url "http://127.0.0.1:$ApiPort/v1/meta" -TimeoutSec 60
if (-not $apiHealth.Ok) {
    Write-AtlasProductError `
        -What "LIVE_API health check failed (/v1/meta)." `
        -Cause $(if ($apiHealth.Error) { $apiHealth.Error } else { "No successful HTTP response within timeout." }) `
        -Action "Inspect $($apiProc.log_stderr). Confirm vault path and that port $ApiPort is free. API binds 127.0.0.1 only." `
        -Retry "powershell -NoProfile -File scripts\windows\atlas-stop.ps1; powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
        -LogPath $errLog
    exit 1
}
Write-Host "OK  API health http://127.0.0.1:$ApiPort/v1/meta"
$env:VITE_ATLAS_API_BASE = "http://127.0.0.1:$ApiPort"

$webUrl = "http://127.0.0.1:$WebPort/"

# --- start web ---
if (-not $SkipWeb) {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npm) {
        Write-AtlasProductError `
            -What "npm disappeared after preflight; web shell not started." `
            -Cause "npm.cmd / npm not on PATH." `
            -Action "Reinstall Node.js LTS, then retry. Playwright is intentionally not installed by this path." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $errLog
        exit 1
    }
    $webDir = Join-Path $repoRoot "apps\web"
    if (-not (Test-Path -LiteralPath (Join-Path $webDir "package.json"))) {
        Write-AtlasProductError `
            -What "apps/web package.json is missing." `
            -Cause "Web shell checkout appears incomplete." `
            -Action "Sync the repository so apps/web exists. Do not add Playwright via this installer." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $errLog
        exit 1
    }
    Ensure-WebDependencies -Npm $npm -WebDir $webDir -ErrLog $errLog
    Write-Host "Starting web (npm run dev) on 127.0.0.1:$WebPort ..."
    $webArgs = "run dev -- --host 127.0.0.1 --port $WebPort"
    $webProc = Start-TrackedProcess -Name "web" -FilePath $npm.Source `
        -ArgumentList $webArgs -WorkingDirectory $webDir -StateDir $stateDir
    [void]$processRecords.Add($webProc)
    Write-Host "  Web pid=$($webProc.pid)"

    $tcpOk = Wait-AtlasTcpOpen -HostName "127.0.0.1" -Port $WebPort -TimeoutSec 90
    if (-not $tcpOk) {
        $webAlive = $false
        try { $webAlive = [bool](Get-Process -Id $webProc.pid -ErrorAction Stop) } catch { $webAlive = $false }
        $stderrHint = ""
        if (Test-Path -LiteralPath $webProc.log_stderr) {
            $stderrHint = (Get-Content -LiteralPath $webProc.log_stderr -Raw -ErrorAction SilentlyContinue)
            if ($stderrHint -and $stderrHint.Length -gt 400) {
                $stderrHint = $stderrHint.Substring(0, 400)
            }
        }
        $cause = "TCP connect to 127.0.0.1:$WebPort timed out."
        if (-not $webAlive) {
            $cause = "Web process exited early before binding port $WebPort."
        }
        if ($stderrHint) {
            $cause = "$cause stderr: $stderrHint"
        }
        Write-AtlasProductError `
            -What "Web shell did not open port $WebPort in time." `
            -Cause $cause `
            -Action "Inspect $($webProc.log_stderr). If Rollup native is missing, delete apps/web/node_modules and retry. Free the port or pass -WebPort. Stop with atlas-stop.ps1." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-stop.ps1; powershell -NoProfile -File scripts\windows\atlas-start.ps1" `
            -LogPath $errLog
        exit 1
    }
    # Prefer HTTP health when Vite answers
    $webHealth = Wait-AtlasHttpOk -Url $webUrl -TimeoutSec 30
    if ($webHealth.Ok) {
        Write-Host "OK  Web health $webUrl"
    }
    else {
        Write-Host "OK  Web port open (HTTP probe soft-fail: $($webHealth.Error))" -ForegroundColor DarkYellow
    }
}

$started = [ordered]@{
    package_id            = "AS-PROD-INSTALL-001"
    productization        = $true
    release_certified     = $false
    pilot_pass            = $false
    not_release           = $true
    stranger_can_start    = $true
    claim                 = "STRANGER_CAN_START_ATLAS"
    note                  = "PRODUCTIZATION local start - NOT RELEASE - NOT PILOT"
    vault_mode            = $vaultMode
    vault_path            = $vaultPath
    runtime_root          = $runtimeRoot
    api_url               = "http://127.0.0.1:$ApiPort/v1/meta"
    web_url               = $(if ($SkipWeb) { $null } else { $webUrl })
    processes             = @($processRecords.ToArray())
}
$started | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $pidFile -Encoding UTF8

Write-Host ""
Write-Host "State written: $pidFile"
Write-Host "Stop with:  powershell -NoProfile -File scripts\windows\atlas-stop.ps1"
Write-Host ""
Write-Host "HONEST STATUS:" -ForegroundColor Yellow
Write-Host "  PRODUCTIZATION / NOT RELEASE" -ForegroundColor Yellow
Write-Host "  RELEASE CERTIFIED = NO" -ForegroundColor Yellow
Write-Host "  PILOT PASS = NO (DORMANT_BLOCKED)" -ForegroundColor Yellow
Write-Host "  STRANGER_CAN_START_ATLAS = YES (local health passed)" -ForegroundColor Green
Write-Host "  API: http://127.0.0.1:$ApiPort/v1/meta"
if (-not $SkipWeb) {
    Write-Host "  Web: $webUrl"
}

if (-not $SkipWeb -and -not $SkipBrowser) {
    try {
        Start-Process $webUrl | Out-Null
        Write-Host "Opened browser to $webUrl"
    }
    catch {
        Write-Host "WARN: could not open browser automatically: $($_.Exception.Message)" -ForegroundColor DarkYellow
        Write-Host "Open manually: $webUrl"
    }
}

Write-Host ""
Write-Host "TIME_TO_FIRST_VALUE target: <=15 minutes for a prepared Windows stranger machine." -ForegroundColor Cyan
exit 0
