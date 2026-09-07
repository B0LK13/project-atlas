param()

$ErrorActionPreference = "Stop"

function Get-CmdVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$Args
    )
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        return "missing"
    }
    $result = & $Command $Args.Split(" ") 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $result) {
        return "present"
    }
    return ($result | Select-Object -First 1).ToString().Trim()
}

function Test-PathSafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [bool](Test-Path -LiteralPath $Path)
}

$report = [ordered]@{
    host = [ordered]@{
        os = (Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption)
        version = (Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Version)
        build = (Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty BuildNumber)
        architecture = $env:PROCESSOR_ARCHITECTURE
        powershell = $PSVersionTable.PSVersion.ToString()
    }
    paths = [ordered]@{
        userprofile = $env:USERPROFILE
        temp = $env:TEMP
        localappdata = $env:LOCALAPPDATA
        appdata = $env:APPDATA
        recommended_worktree_root = "D:\atlas-worktrees"
    }
    tools = [ordered]@{
        git = (Get-CmdVersion -Command "git" -Args "--version")
        gh = (Get-CmdVersion -Command "gh" -Args "--version")
        py = (Get-CmdVersion -Command "py" -Args "-3.12 --version")
        uv = (Get-CmdVersion -Command "uv" -Args "--version")
        node = (Get-CmdVersion -Command "node" -Args "--version")
        npm = (Get-CmdVersion -Command "npm" -Args "--version")
        pnpm = (Get-CmdVersion -Command "pnpm" -Args "--version")
        docker = (Get-CmdVersion -Command "docker" -Args "--version")
        winget = (Get-CmdVersion -Command "winget" -Args "--version")
    }
    mcp_config = [ordered]@{
        copilot = Test-PathSafe "$($env:USERPROFILE)\.copilot\mcp-config.json"
        vscode = Test-PathSafe "$($env:APPDATA)\Code\User\mcp.json"
        cursor = Test-PathSafe "$($env:USERPROFILE)\.cursor\mcp.json"
        github_wrapper = Test-PathSafe "$($env:USERPROFILE)\.local\bin\github-mcp-wrapper.ps1"
    }
    github_auth = [ordered]@{
        gh_auth_status = (if (Get-Command gh -ErrorAction SilentlyContinue) { (& gh auth status 2>$null | Select-Object -First 1) } else { "gh-missing" })
    }
}

$report | ConvertTo-Json -Depth 5
