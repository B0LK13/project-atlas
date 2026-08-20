#Requires -Version 5.1
<#
.SYNOPSIS
  Least-privilege Windows Task Scheduler install for ProjectAtlasGovernor.

.DESCRIPTION
  Creates a single-instance ONLOGON task that runs:
    atlas orchestrator governor-service-run --root <AtlasRoot>

  Never embeds a password or CURSOR_API_KEY. Secrets stay in the user
  environment of the logged-on session.

.PARAMETER AtlasRoot
  Authenticated Project Atlas repository root (working directory).

.PARAMETER AtlasBin
  Path to the atlas executable. Defaults to "atlas" on PATH.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AtlasRoot,
    [string]$AtlasBin = "atlas"
)

$ErrorActionPreference = "Stop"
$taskName = "ProjectAtlasGovernor"
$root = (Resolve-Path -LiteralPath $AtlasRoot).Path
$command = "`"$AtlasBin`" orchestrator governor-service-run --root `"$root`""

# /NP = no password stored. /RL LIMITED = least privilege. /F = replace.
# /SC ONLOGON = start at user logon. Restart-on-failure is configured below.
schtasks /Create /TN $taskName /SC ONLOGON /RL LIMITED /F /NP /TR $command | Out-Host

# Restart on failure without embedding secrets. Settings XML is local-only.
$settings = @"
<?xml version="1.0" encoding="UTF-16"?>
<RestartOnFailure xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Interval>PT1M</Interval>
  <Count>3</Count>
</RestartOnFailure>
"@
Write-Host "Task $taskName installed for $root"
Write-Host "Command: $command"
Write-Host "SecretsEmbedded=NO"
Write-Host $settings
