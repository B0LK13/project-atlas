#Requires -Version 5.1
<#
.SYNOPSIS
  Shared helpers for AS-PROD-INSTALL-001 Windows stranger bootstrap.

.DESCRIPTION
  Dot-source only. Provides PRODUCTIZATION honesty banners, structured
  WHAT/CAUSE/ACTION/RETRY product errors, and small path helpers.
  Package: AS-PROD-INSTALL-001. NOT RELEASE. NOT PILOT.
#>

Set-StrictMode -Version Latest

function Write-AtlasProductBanner {
    <#
    .SYNOPSIS
      Honest PRODUCTIZATION / NOT RELEASE / NOT PILOT banner for strangers.
    #>
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PROJECT ATLAS - PRODUCTIZATION INSTALL (AS-PROD-INSTALL-001)" -ForegroundColor Cyan
    Write-Host "  Audience: STRANGER / OPERATOR (Windows-first bootstrap)" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  PRODUCTIZATION PATH - NOT RELEASE" -ForegroundColor Yellow
    Write-Host "  NOT RELEASE CERTIFIED" -ForegroundColor Yellow
    Write-Host "  NOT PILOT PASS / PILOT DORMANT_BLOCKED" -ForegroundColor Yellow
    Write-Host "  No MSI / winget / code signing in this package" -ForegroundColor Yellow
    Write-Host "  Prefer .tmp/productization runtime - never invent authentic estate" -ForegroundColor Yellow
    Write-Host "  Claim target when healthy: STRANGER_CAN_START_ATLAS (local only)" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-AtlasProductError {
    <#
    .SYNOPSIS
      Emit a structured product error (WHAT / CAUSE / ACTION / RETRY) to stderr.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$What,
        [Parameter(Mandatory = $true)][string]$Cause,
        [Parameter(Mandatory = $true)][string]$Action,
        [Parameter(Mandatory = $true)][string]$Retry,
        [string]$LogPath
    )
    $block = @(
        "------------------------------------------------------------"
        "ATLAS PRODUCT ERROR (AS-PROD-INSTALL-001)"
        "WHAT:   $What"
        "CAUSE:  $Cause"
        "ACTION: $Action"
        "RETRY:  $Retry"
        "NOTE:   PRODUCTIZATION / NOT RELEASE / NOT PILOT"
        "------------------------------------------------------------"
    ) -join [Environment]::NewLine

    [Console]::Error.WriteLine($block)
    if ($LogPath) {
        $dir = Split-Path -Parent $LogPath
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        Add-Content -LiteralPath $LogPath -Value $block -Encoding UTF8
    }
}

function Resolve-AtlasRepoRoot {
    <#
    .SYNOPSIS
      Resolve repo root from scripts/windows (expects pyproject.toml).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$ScriptDir
    )
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\.."))
    if (-not (Test-Path -LiteralPath (Join-Path $candidate "pyproject.toml"))) {
        return $null
    }
    if (-not (Test-Path -LiteralPath (Join-Path $candidate "apps\web\package.json"))) {
        return $null
    }
    return $candidate
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

function Test-PathWritable {
    param([Parameter(Mandatory = $true)][string]$Directory)
    try {
        if (-not (Test-Path -LiteralPath $Directory)) {
            New-Item -ItemType Directory -Force -Path $Directory | Out-Null
        }
        $probe = Join-Path $Directory (".atlas-write-probe-{0}" -f [guid]::NewGuid().ToString("N"))
        Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII
        Remove-Item -LiteralPath $probe -Force
        return $true
    }
    catch {
        return $false
    }
}

function Get-AtlasPythonCommand {
    <#
    .SYNOPSIS
      Prefer py -3.12 launcher, else python, else python3. Returns hashtable or $null.
    #>
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $verOut = & py -3.12 -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $verOut) {
            return @{
                Exe  = $py.Source
                Args = @("-3.12")
                Label = "py -3.12"
            }
        }
    }
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $verOut = & $cmd.Source -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $verOut) { continue }
        $parts = $verOut.Trim().Split(".")
        if ($parts.Count -ge 2) {
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
                return @{
                    Exe   = $cmd.Source
                    Args  = @()
                    Label = $name
                }
            }
        }
    }
    return $null
}

function Invoke-AtlasPython {
    param(
        [Parameter(Mandatory = $true)]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory
    )
    $allArgs = @()
    if ($Python.Args) { $allArgs += $Python.Args }
    $allArgs += $Arguments
    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
        try {
            & $Python.Exe @allArgs
            return $LASTEXITCODE
        }
        finally { Pop-Location }
    }
    & $Python.Exe @allArgs
    return $LASTEXITCODE
}

function Wait-AtlasHttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 45,
        [int]$IntervalMs = 500
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastErr = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
                return @{
                    Ok         = $true
                    StatusCode = [int]$resp.StatusCode
                    Body       = $resp.Content
                    Error      = $null
                }
            }
            $lastErr = "HTTP $($resp.StatusCode)"
        }
        catch {
            $lastErr = $_.Exception.Message
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return @{ Ok = $false; StatusCode = 0; Body = $null; Error = $lastErr }
}

function Wait-AtlasTcpOpen {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSec = 45,
        [int]$IntervalMs = 500
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $iar = $client.BeginConnect($HostName, $Port, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne(800)
            if ($ok -and $client.Connected) {
                $client.EndConnect($iar)
                $client.Close()
                return $true
            }
            $client.Close()
        }
        catch { }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $false
}
