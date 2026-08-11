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
    # Isolate exit code from stdout/stderr. If callers assign `$code = Invoke-AtlasPython ...`,
    # any success-stream output is captured into $code (Object[]), and `$code -ne 0` becomes a
    # non-empty filter result (truthy) even when pip succeeded — false "install failed" (C-INSTALL).
    $allArgs = @()
    if ($Python.Args) { $allArgs += $Python.Args }
    $allArgs += $Arguments
    $invoke = {
        $output = & $Python.Exe @allArgs 2>&1
        $code = [int]$LASTEXITCODE
        foreach ($line in @($output)) {
            Write-Host ([string]$line)
        }
        return $code
    }
    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
        try {
            return (& $invoke)
        }
        finally { Pop-Location }
    }
    return (& $invoke)
}

function Wait-AtlasHttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 45,
        [int]$IntervalMs = 500,
        # SEC-009: optional per-launch Bearer for LIVE_API health after api-serve mint.
        [string]$BearerToken = ""
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastErr = $null
    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($BearerToken)) {
        $headers["Authorization"] = "Bearer $($BearerToken.Trim())"
    }
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = if ($headers.Count -gt 0) {
                Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -Headers $headers
            } else {
                Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            }
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

function Protect-AtlasSensitiveFile {
    <#
    .SYNOPSIS
      SEC-ADV004-B-002 / Wave B: strip inheritance; current user modify only.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    try {
        icacls $Path /inheritance:r | Out-Null
        icacls $Path /grant:r "${env:USERNAME}:(M)" | Out-Null
    }
    catch {
        # Best-effort ACL; caller may still scrub secrets from content.
    }
}

function Clear-AtlasSecretFromLog {
    <#
    .SYNOPSIS
      Replace a known secret span in a log file, then harden ACL.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$Secret
    )
    if ([string]::IsNullOrWhiteSpace($Secret)) { return }
    if (-not (Test-Path -LiteralPath $LogPath)) { return }
    try {
        $raw = [string](Get-Content -LiteralPath $LogPath -Raw -ErrorAction Stop)
        if ($raw.Contains($Secret)) {
            $scrubbed = $raw.Replace($Secret, "[redacted]")
            Set-Content -LiteralPath $LogPath -Value $scrubbed -NoNewline -Encoding utf8
        }
    }
    catch { }
    Protect-AtlasSensitiveFile -Path $LogPath
}

function Wait-AtlasApiReadToken {
    <#
    .SYNOPSIS
      Capture per-launch READ token (SEC-009). Prefer TokenFilePath
      (ATLAS_API_TOKEN_FILE); fall back to non-redacted stderr line.
      Never logs the token value.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$StderrLogPath,
        [string]$TokenFilePath = "",
        [int]$TimeoutSec = 30,
        [int]$IntervalMs = 200
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (-not [string]::IsNullOrWhiteSpace($TokenFilePath) -and (Test-Path -LiteralPath $TokenFilePath)) {
            $fromFile = [string](Get-Content -LiteralPath $TokenFilePath -Raw -ErrorAction SilentlyContinue)
            if (-not [string]::IsNullOrWhiteSpace($fromFile)) {
                return $fromFile.Trim()
            }
        }
        if (Test-Path -LiteralPath $StderrLogPath) {
            $raw = [string](Get-Content -LiteralPath $StderrLogPath -Raw -ErrorAction SilentlyContinue)
            if ($raw -match '(?m)^ATLAS_API_READ_TOKEN=(\S+)\s*$') {
                $candidate = $Matches[1]
                if ($candidate -notmatch '^\[redacted') {
                    return $candidate
                }
            }
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $null
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

function Test-AtlasPortFree {
    <#
    .SYNOPSIS
      Return $true when no listener is bound on 127.0.0.1 (or ::1) for the port.
      Used before start to avoid false-positive health against a foreign process.
    #>
    param(
        [Parameter(Mandatory = $true)][int]$Port
    )
    try {
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        $listeners = @()
    }
    foreach ($c in $listeners) {
        $addr = [string]$c.LocalAddress
        if ($addr -eq "127.0.0.1" -or $addr -eq "::1" -or $addr -eq "0.0.0.0" -or $addr -eq "::") {
            return $false
        }
    }
    return $true
}

function Test-AtlasProcessOwnsPort {
    <#
    .SYNOPSIS
      True when the Listen owner for Host:Port is $RootPid or a descendant (Windows atlas.exe -> python child).
    #>
    param(
        [Parameter(Mandatory = $true)][int]$RootPid,
        [Parameter(Mandatory = $true)][int]$Port,
        [string]$HostName = "127.0.0.1"
    )
    try {
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        return $false
    }
    $allowed = New-Object "System.Collections.Generic.HashSet[int]"
    [void]$allowed.Add($RootPid)
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$allowed.Add([int]$_.ProcessId) }
    }
    catch { }

    foreach ($c in $listeners) {
        $addr = [string]$c.LocalAddress
        if ($HostName -and $addr -ne $HostName -and $addr -ne "0.0.0.0" -and $addr -ne "::") {
            continue
        }
        if ($allowed.Contains([int]$c.OwningProcess)) {
            return $true
        }
    }
    return $false
}

# --- SEC-025 / SEC-026 / SEC-029: process identity + loopback bind proofs ---

function New-AtlasSessionNonce {
    <#
    .SYNOPSIS
      Opaque per-launch session nonce (SEC-025/026). Bound into every process record.
    #>
    return [guid]::NewGuid().ToString("N")
}

function Get-AtlasListeningPortsForPid {
    param([Parameter(Mandatory = $true)][int]$ProcessId)
    $ports = New-Object "System.Collections.Generic.List[int]"
    try {
        $listeners = @(Get-NetTCPConnection -OwningProcess $ProcessId -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        $listeners = @()
    }
    foreach ($c in $listeners) {
        $p = [int]$c.LocalPort
        if (-not $ports.Contains($p)) { [void]$ports.Add($p) }
    }
    return @($ports.ToArray() | Sort-Object)
}

function Get-AtlasLiveProcessIdentity {
    <#
    .SYNOPSIS
      Snapshot live Windows process fields used for SEC-025 verify-before-kill.
    #>
    param([Parameter(Mandatory = $true)][int]$ProcessId)
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction Stop
    }
    catch {
        return $null
    }
    $cim = $null
    try {
        $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    }
    catch { }
    $creation = $null
    if ($proc.StartTime) {
        $creation = $proc.StartTime.ToUniversalTime().ToString("o")
    }
    elseif ($cim -and $cim.CreationDate) {
        $creation = ([System.Management.ManagementDateTimeConverter]::ToDateTime($cim.CreationDate)).ToUniversalTime().ToString("o")
    }
    $exe = $null
    if ($cim -and $cim.ExecutablePath) { $exe = [string]$cim.ExecutablePath }
    elseif ($proc.Path) { $exe = [string]$proc.Path }
    $cmdline = $null
    if ($cim -and $null -ne $cim.CommandLine) { $cmdline = [string]$cim.CommandLine }
    $parent = $null
    if ($cim -and $null -ne $cim.ParentProcessId) { $parent = [int]$cim.ParentProcessId }
    return [pscustomobject]@{
        pid              = $ProcessId
        creation_date    = $creation
        executable_path  = $exe
        command_line     = $cmdline
        parent_pid       = $parent
        ports            = @(Get-AtlasListeningPortsForPid -ProcessId $ProcessId)
        process_name     = [string]$proc.ProcessName
    }
}

function New-AtlasProcessIdentityRecord {
    <#
    .SYNOPSIS
      Build a durable process identity record immediately after spawn (SEC-025/026).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$SessionNonce,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ArgumentList,
        [int[]]$ExpectedPorts = @(),
        [string]$LogStdout = "",
        [string]$LogStderr = ""
    )
    # Brief settle so StartTime / CIM are queryable after Start-Process.
    Start-Sleep -Milliseconds 50
    $live = Get-AtlasLiveProcessIdentity -ProcessId $ProcessId
    $creation = $null
    $exe = $FilePath
    $cmdline = ("{0} {1}" -f $FilePath, $ArgumentList).Trim()
    $parent = $null
    $ports = @($ExpectedPorts)
    if ($live) {
        if ($live.creation_date) { $creation = $live.creation_date }
        if ($live.executable_path) { $exe = $live.executable_path }
        if ($live.command_line) { $cmdline = $live.command_line }
        if ($null -ne $live.parent_pid) { $parent = [int]$live.parent_pid }
        if ($live.ports -and $live.ports.Count -gt 0) { $ports = @($live.ports) }
    }
    return [pscustomobject]@{
        identity_schema   = "atlas-process-identity/v1"
        name              = $Name
        pid               = $ProcessId
        creation_date     = $creation
        executable_path   = $exe
        command_line      = $cmdline
        working_directory = [System.IO.Path]::GetFullPath($WorkingDirectory)
        session_nonce     = $SessionNonce
        ports             = @($ports)
        parent_pid        = $parent
        spawn_file_path   = $FilePath
        spawn_arguments   = $ArgumentList
        log_stdout        = $LogStdout
        log_stderr        = $LogStderr
        provisional       = $true
    }
}

function Test-AtlasProcessIdentityMatch {
    <#
    .SYNOPSIS
      Verify live process matches recorded identity. Mismatch => fail-closed (no kill).
    #>
    param([Parameter(Mandatory = $true)]$Record)

    function Get-AtlasRecordProp {
        param($Obj, [string]$Name)
        if ($null -eq $Obj) { return $null }
        $prop = $Obj.PSObject.Properties[$Name]
        if ($null -eq $prop) { return $null }
        return $prop.Value
    }

    $procId = [int](Get-AtlasRecordProp $Record "pid")
    if ($procId -le 0) {
        return @{ Ok = $false; Reason = "pid_missing"; Detail = "record lacks pid" }
    }
    $live = Get-AtlasLiveProcessIdentity -ProcessId $procId
    if (-not $live) {
        return @{ Ok = $false; Reason = "process_gone"; Detail = "pid=$procId not running" }
    }

    $recCreation = Get-AtlasRecordProp $Record "creation_date"
    if ([string]::IsNullOrWhiteSpace([string]$recCreation)) {
        return @{ Ok = $false; Reason = "creation_date_missing"; Detail = "refuse kill without recorded creation_date (SEC-025)" }
    }
    if (-not $live.creation_date) {
        return @{ Ok = $false; Reason = "creation_date_missing_live"; Detail = "cannot verify StartTime" }
    }
    try {
        $recDt = [datetime]::Parse([string]$recCreation, $null, [System.Globalization.DateTimeStyles]::RoundtripKind)
        $liveDt = [datetime]::Parse($live.creation_date, $null, [System.Globalization.DateTimeStyles]::RoundtripKind)
        if ([math]::Abs(($recDt - $liveDt).TotalSeconds) -gt 1.0) {
            return @{
                Ok     = $false
                Reason = "creation_date_mismatch"
                Detail = "recorded=$recCreation live=$($live.creation_date) (possible PID reuse)"
            }
        }
    }
    catch {
        return @{ Ok = $false; Reason = "creation_date_parse"; Detail = $_.Exception.Message }
    }

    $recExe = Get-AtlasRecordProp $Record "executable_path"
    if ([string]::IsNullOrWhiteSpace([string]$recExe)) {
        return @{ Ok = $false; Reason = "executable_path_missing"; Detail = "refuse kill without recorded executable_path (SEC-025)" }
    }
    if (-not $live.executable_path) {
        return @{ Ok = $false; Reason = "executable_path_missing_live"; Detail = "cannot verify ExecutablePath" }
    }
    $a = [System.IO.Path]::GetFullPath([string]$recExe)
    $b = [System.IO.Path]::GetFullPath([string]$live.executable_path)
    if (-not $a.Equals($b, [System.StringComparison]::OrdinalIgnoreCase)) {
        return @{
            Ok     = $false
            Reason = "executable_path_mismatch"
            Detail = "recorded=$a live=$b"
        }
    }

    $recCl = Get-AtlasRecordProp $Record "command_line"
    if ([string]::IsNullOrWhiteSpace([string]$recCl)) {
        return @{ Ok = $false; Reason = "command_line_missing"; Detail = "refuse kill without recorded command_line (SEC-025)" }
    }
    if (-not $live.command_line) {
        return @{ Ok = $false; Reason = "command_line_missing_live"; Detail = "cannot verify CommandLine" }
    }
    $recClS = ([string]$recCl).Trim()
    $liveCl = ([string]$live.command_line).Trim()
    if (-not $recClS.Equals($liveCl, [System.StringComparison]::OrdinalIgnoreCase)) {
        $recLeaf = [System.IO.Path]::GetFileName(($recClS -split '\s+')[0].Trim('"'))
        $liveLeaf = [System.IO.Path]::GetFileName(($liveCl -split '\s+')[0].Trim('"'))
        if (-not $recLeaf.Equals($liveLeaf, [System.StringComparison]::OrdinalIgnoreCase)) {
            return @{
                Ok     = $false
                Reason = "command_line_mismatch"
                Detail = "recorded exe leaf=$recLeaf live=$liveLeaf"
            }
        }
    }

    $recParent = Get-AtlasRecordProp $Record "parent_pid"
    if ($null -eq $recParent -or [string]::IsNullOrWhiteSpace([string]$recParent)) {
        return @{ Ok = $false; Reason = "parent_pid_missing"; Detail = "refuse kill without recorded parent_pid (SEC-025)" }
    }
    if ($null -eq $live.parent_pid) {
        return @{ Ok = $false; Reason = "parent_pid_missing_live"; Detail = "cannot verify ParentProcessId" }
    }
    if ([int]$recParent -ne [int]$live.parent_pid) {
        return @{
            Ok     = $false
            Reason = "parent_pid_mismatch"
            Detail = "recorded=$recParent live=$($live.parent_pid)"
        }
    }

    $recWd = Get-AtlasRecordProp $Record "working_directory"
    if ([string]::IsNullOrWhiteSpace([string]$recWd)) {
        return @{ Ok = $false; Reason = "working_directory_missing"; Detail = "refuse kill without recorded working_directory (SEC-025)" }
    }

    $nonce = Get-AtlasRecordProp $Record "session_nonce"
    if ([string]::IsNullOrWhiteSpace([string]$nonce)) {
        return @{ Ok = $false; Reason = "session_nonce_missing"; Detail = "legacy pid-only record; refuse kill" }
    }

    return @{ Ok = $true; Reason = "match"; Detail = "identity verified for pid=$procId"; Live = $live }
}

function Stop-AtlasVerifiedProcess {
    <#
    .SYNOPSIS
      SEC-025: verify identity then Stop-Process. On mismatch: FAIL CLOSED, no kill.
    #>
    param(
        [Parameter(Mandatory = $true)]$Record,
        [switch]$Quiet
    )
    $name = [string]$Record.name
    $procId = [int]$Record.pid
    $match = Test-AtlasProcessIdentityMatch -Record $Record
    if (-not $match.Ok) {
        if ($match.Reason -eq "process_gone") {
            if (-not $Quiet) {
                Write-Host "  pid=$procId already gone ($name)" -ForegroundColor DarkYellow
            }
            return @{ Stopped = $false; Verified = $false; Reason = $match.Reason; Orphan = $false }
        }
        Write-AtlasProductError `
            -What "Refusing to stop process '$name' (pid=$procId): identity mismatch (SEC-025 fail-closed)." `
            -Cause "$($match.Reason): $($match.Detail)" `
            -Action "Inspect the live process manually. Do not force-kill by PID alone. Re-run atlas-stop only against a matching atlas-pids.json session." `
            -Retry "powershell -NoProfile -File scripts\windows\atlas-stop.ps1"
        return @{ Stopped = $false; Verified = $false; Reason = $match.Reason; Orphan = $true; FailClosed = $true }
    }

    if (-not $Quiet) {
        Write-Host "Stopping $name pid=$procId (identity verified)..."
    }
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
    }
    catch {
        if (-not $Quiet) {
            Write-Host "  Stop-Process pid=${procId}: $($_.Exception.Message)" -ForegroundColor DarkYellow
        }
    }

    # Children: only after parent identity verified. Kill direct children of this pid.
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
            ForEach-Object {
                $childPid = [int]$_.ProcessId
                if (-not $Quiet) {
                    Write-Host "  stopping verified-parent child pid=$childPid $($_.Name)"
                }
                Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
            }
    }
    catch { }

    return @{ Stopped = $true; Verified = $true; Reason = "ok"; Orphan = $false }
}

function Stop-AtlasVerifiedSession {
    <#
    .SYNOPSIS
      Stop all recorded session processes with SEC-025 verify-before-kill.
      Returns ORPHAN_PROCESS_COUNT for SEC-026 (verified session members still alive after stop attempt).
    #>
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Processes,
        [string]$SessionNonce = "",
        [switch]$Quiet
    )
    $orphan = 0
    $failClosed = 0
    foreach ($procInfo in @($Processes)) {
        if ($SessionNonce -and $procInfo.session_nonce -and ([string]$procInfo.session_nonce -ne $SessionNonce)) {
            if (-not $Quiet) {
                Write-Host "  skip pid=$($procInfo.pid) (session_nonce mismatch; foreign session)" -ForegroundColor DarkYellow
            }
            continue
        }
        $result = Stop-AtlasVerifiedProcess -Record $procInfo -Quiet:$Quiet
        $fc = $false
        $orph = $false
        $stopped = $false
        if ($null -ne $result) {
            $fcProp = $result.PSObject.Properties["FailClosed"]
            if ($null -ne $fcProp -and $fcProp.Value) { $fc = [bool]$fcProp.Value }
            $orProp = $result.PSObject.Properties["Orphan"]
            if ($null -ne $orProp -and $orProp.Value) { $orph = [bool]$orProp.Value }
            $stProp = $result.PSObject.Properties["Stopped"]
            if ($null -ne $stProp -and $stProp.Value) { $stopped = [bool]$stProp.Value }
        }
        if ($fc) { $failClosed++ }
        if ($orph) { $orphan++ }
        elseif ($stopped) {
            Start-Sleep -Milliseconds 100
            if (Get-Process -Id ([int]$procInfo.pid) -ErrorAction SilentlyContinue) {
                $orphan++
            }
        }
    }
    return @{
        ORPHAN_PROCESS_COUNT = $orphan
        FAIL_CLOSED_COUNT    = $failClosed
    }
}

function Write-AtlasSessionState {
    <#
    .SYNOPSIS
      Persist provisional/final session process identities (SEC-026 immediate bind).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][string]$SessionNonce,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Processes,
        [hashtable]$Extra = @{}
    )
    $payload = [ordered]@{
        package_id            = "AS-PROD-INSTALL-001"
        identity_schema       = "atlas-process-identity/v1"
        session_nonce         = $SessionNonce
        productization        = $true
        release_certified     = $false
        pilot_pass            = $false
        not_release           = $true
        processes             = @($Processes)
    }
    foreach ($k in $Extra.Keys) {
        $payload[$k] = $Extra[$k]
    }
    $dir = Split-Path -Parent $PidFile
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $PidFile -Encoding UTF8
}

function Assert-AtlasLoopbackOnly {
    <#
    .SYNOPSIS
      SEC-029: FAIL if any Listen on Port is bound to 0.0.0.0 or :: (non-loopback all-interfaces).
      Pass when listeners are only 127.0.0.1 / ::1 (or no listener yet).
    #>
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [string]$Label = "service"
    )
    try {
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        $listeners = @()
    }
    $bad = @()
    $ok = @()
    foreach ($c in $listeners) {
        $addr = [string]$c.LocalAddress
        if ($addr -eq "0.0.0.0" -or $addr -eq "::") {
            $bad += "pid=$($c.OwningProcess) addr=$addr port=$Port"
        }
        elseif ($addr -eq "127.0.0.1" -or $addr -eq "::1") {
            $ok += "pid=$($c.OwningProcess) addr=$addr"
        }
        else {
            # Other specific addresses — treat as non-default; fail closed for productization bind.
            $bad += "pid=$($c.OwningProcess) addr=$addr port=$Port (non-loopback)"
        }
    }
    if ($bad.Count -gt 0) {
        return @{
            Ok      = $false
            Detail  = "$Label port $Port has non-loopback listener(s): $($bad -join '; ')"
            Bad     = $bad
            OkBinds = $ok
        }
    }
    return @{ Ok = $true; Detail = "$Label port $Port loopback-only (or unbound)"; Bad = @(); OkBinds = $ok }
}
