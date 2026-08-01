[CmdletBinding()]
param(
    [switch]$ClaudeOnly,
    [switch]$CursorOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$SkillId = "atlas-vault-documentation"

function Install-Skill([string]$TargetRoot) {
    $Target = Join-Path $TargetRoot $SkillId
    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
    if (Test-Path $Target) {
        Remove-Item -Recurse -Force $Target
    }
    Copy-Item -Recurse -Force $SkillDir $Target
    foreach ($Name in @(".git", "tests")) {
        $RemovePath = Join-Path $Target $Name
        if (Test-Path $RemovePath) {
            Remove-Item -Recurse -Force $RemovePath
        }
    }
    Write-Host "Installed $Target"
}

if (-not $CursorOnly) {
    Install-Skill (Join-Path $HOME ".claude\\skills")
}
if (-not $ClaudeOnly) {
    Install-Skill (Join-Path $HOME ".cursor\\skills")
}

Write-Host ""
Write-Host "Verify with:"
Write-Host "  mda --check"
Write-Host "  mda --skill $SkillId --dry-run <raw-event.md>"
