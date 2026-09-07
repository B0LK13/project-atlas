param(
    [switch]$Check,
    [switch]$DryRun,
    [switch]$Install
)

$ErrorActionPreference = "Stop"

if (-not ($Check -or $DryRun -or $Install)) {
    $Check = $true
}

$modeCount = @($Check, $DryRun, $Install | Where-Object { $_ }).Count
if ($modeCount -gt 1) {
    Write-Host "usage: .\scripts\bootstrap-dev-tooling.ps1 [-Check|-DryRun|-Install]"
    exit 2
}

$Mode = if ($Install) { "Install" } elseif ($DryRun) { "DryRun" } else { "Check" }
Write-Host "mode=$Mode"

$Pinned = [ordered]@{
    "codebase-memory-mcp" = "0.10.8"
    "@playwright/mcp" = "0.0.80"
    "@upstash/context7-mcp" = "4.0.5"
    "markdownlint-cli2" = "0.23.2"
}

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Write-PresentOrMissing {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Present
    )
    if ($Present) {
        Write-Host "ok: $Name"
    } else {
        Write-Host "missing: $Name"
    }
}

function Install-NpmPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Version
    )
    $spec = "$Name@$Version"
    $hasName = (& npm list -g --depth=0 $Name 2>$null | Out-String)
    if ($LASTEXITCODE -eq 0 -and $hasName -match [regex]::Escape($spec)) {
        Write-Host "present npm: $spec"
        return
    }
    if ($Mode -eq "Install") {
        & npm install -g $spec --no-fund --no-audit
    } else {
        Write-Host "would install npm: $spec"
    }
}

function Install-PipxPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Package,
        [Parameter(Mandatory = $true)][string]$Binary
    )
    if (Test-Command $Binary) {
        Write-Host "present pipx: $Package"
        return
    }
    if (-not (Test-Command "pipx")) {
        Write-Host "missing prerequisite: pipx (required for $Package)"
        return
    }
    if ($Mode -eq "Install") {
        & pipx install $Package
    } else {
        Write-Host "would install pipx: $Package"
    }
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$CommandName
    )
    if (Test-Command $CommandName) {
        Write-Host "present command: $CommandName ($Id)"
        return
    }
    if ($Mode -ne "Install") {
        Write-Host "would install winget: $Id"
        return
    }
    if (-not (Test-Command "winget")) {
        Write-Host "missing prerequisite: winget (cannot install $Id)"
        return
    }
    & winget install --id $Id --exact --scope user --accept-source-agreements --accept-package-agreements
}

foreach ($kv in $Pinned.GetEnumerator()) {
    Install-NpmPackage -Name $kv.Key -Version $kv.Value
}

Install-PipxPackage -Package "semgrep==1.176.1" -Binary "semgrep"
Install-PipxPackage -Package "pip-audit==2.10.1" -Binary "pip-audit"
Install-PipxPackage -Package "yamllint==1.38.0" -Binary "yamllint"
Install-PipxPackage -Package "pre-commit==4.6.2" -Binary "pre-commit"

Install-WingetPackage -Id "Gitleaks.Gitleaks" -CommandName "gitleaks"
Install-WingetPackage -Id "AquaSecurity.Trivy" -CommandName "trivy"
Install-WingetPackage -Id "Anchore.Syft" -CommandName "syft"
Install-WingetPackage -Id "Anchore.Grype" -CommandName "grype"
Install-WingetPackage -Id "rhysd.actionlint" -CommandName "actionlint"
Install-WingetPackage -Id "tamasfe.taplo" -CommandName "taplo"
Install-WingetPackage -Id "hadolint.hadolint" -CommandName "hadolint"

Write-PresentOrMissing -Name "git" -Present (Test-Command "git")
Write-PresentOrMissing -Name "gh" -Present (Test-Command "gh")
Write-PresentOrMissing -Name "py" -Present (Test-Command "py")
Write-PresentOrMissing -Name "uv" -Present (Test-Command "uv")
Write-PresentOrMissing -Name "node" -Present (Test-Command "node")
Write-PresentOrMissing -Name "npm" -Present (Test-Command "npm")
Write-PresentOrMissing -Name "pnpm" -Present (Test-Command "pnpm")
Write-PresentOrMissing -Name "docker" -Present (Test-Command "docker")
Write-PresentOrMissing -Name "codebase-memory-mcp" -Present (Test-Command "codebase-memory-mcp")
Write-PresentOrMissing -Name "semgrep" -Present (Test-Command "semgrep")
Write-PresentOrMissing -Name "gitleaks" -Present (Test-Command "gitleaks")
Write-PresentOrMissing -Name "trivy" -Present (Test-Command "trivy")
Write-PresentOrMissing -Name "syft" -Present (Test-Command "syft")
Write-PresentOrMissing -Name "grype" -Present (Test-Command "grype")
Write-PresentOrMissing -Name "actionlint" -Present (Test-Command "actionlint")
Write-PresentOrMissing -Name "markdownlint-cli2" -Present (Test-Command "markdownlint-cli2")
Write-PresentOrMissing -Name "taplo" -Present (Test-Command "taplo")
Write-PresentOrMissing -Name "pip-audit" -Present (Test-Command "pip-audit")
