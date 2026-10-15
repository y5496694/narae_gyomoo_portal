[CmdletBinding()]
param(
    [string]$SkillsDirectory = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }),
    [switch]$Update
)
$ErrorActionPreference = 'Stop'
# A child Windows PowerShell may inherit another PowerShell version's module path.
foreach ($portalModule in @('Microsoft.PowerShell.Management', 'Microsoft.PowerShell.Utility')) {
    Import-Module (Join-Path $PSHOME "Modules\$portalModule") -ErrorAction Stop
}
$portalSkillsRoot = [IO.Path]::GetFullPath($SkillsDirectory).TrimEnd('\', '/')
if ($portalSkillsRoot -eq [IO.Path]::GetPathRoot($portalSkillsRoot).TrimEnd('\', '/')) {
    throw 'Choose a skills directory, not a drive root.'
}
if ((Test-Path -LiteralPath $portalSkillsRoot) -and -not (Test-Path -LiteralPath $portalSkillsRoot -PathType Container)) {
    throw 'SkillsDirectory must be a directory.'
}

function Get-PackFiles([string]$Directory) {
    @(Get-ChildItem -LiteralPath $Directory -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
    })
}

function Test-SamePackFiles([string]$Source, [string]$Target) {
    foreach ($portalFile in (Get-PackFiles $Source)) {
        $portalRelative = $portalFile.FullName.Substring($Source.Length + 1)
        $portalOther = Join-Path $Target $portalRelative
        if (-not (Test-Path -LiteralPath $portalOther -PathType Leaf)) { return $false }
        if ((Get-FileHash -LiteralPath $portalFile.FullName -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $portalOther -Algorithm SHA256).Hash) { return $false }
    }
    return $true
}

$portalJobs = @()
foreach ($portalName in @('narae-gyomu-work-portal', 'narae-gyomu-neis', 'narae-gyomu-edufine', 'wxs-cli')) {
    $portalJobs += [pscustomobject]@{
        Name = $portalName
        Source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "skills\$portalName"))
        Target = [IO.Path]::GetFullPath((Join-Path $portalSkillsRoot $portalName))
        Same = $false
    }
}
# Migrate the old name only on machines where it is already installed.
if (Test-Path -LiteralPath (Join-Path $portalSkillsRoot 'gyomunarae-neis-edufine')) {
    $portalJobs += [pscustomobject]@{
        Name = 'gyomunarae-neis-edufine'
        Source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'compat\gyomunarae-neis-edufine'))
        Target = [IO.Path]::GetFullPath((Join-Path $portalSkillsRoot 'gyomunarae-neis-edufine'))
        Same = $false
    }
}

# Preflight all destinations before copying any files.
foreach ($portalJob in $portalJobs) {
    if ((Split-Path -Parent $portalJob.Target) -ne $portalSkillsRoot) { throw 'Target must be an immediate child of SkillsDirectory.' }
    if (-not (Test-Path -LiteralPath (Join-Path $portalJob.Source 'SKILL.md') -PathType Leaf)) { throw "Incomplete pack: $($portalJob.Name)" }
    if (Test-Path -LiteralPath $portalJob.Target) {
        if (-not (Test-Path -LiteralPath $portalJob.Target -PathType Container)) { throw "Target is not a directory: $($portalJob.Target)" }
        $portalLinks = @(Get-Item -LiteralPath $portalJob.Target; Get-ChildItem -LiteralPath $portalJob.Target -Recurse -Force)
        if ($portalLinks | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
            throw "Linked destination is not supported: $($portalJob.Target)"
        }
        $portalJob.Same = Test-SamePackFiles $portalJob.Source $portalJob.Target
        if (-not $portalJob.Same -and -not $Update) {
            throw "Different installation exists. Use -Update to back up and update: $($portalJob.Target)"
        }
    }
}

$portalBackupRoot = $null
$portalChanged = @($portalJobs | Where-Object { -not $_.Same -and (Test-Path -LiteralPath $_.Target) })
if ($portalChanged.Count -gt 0) {
    $portalBackupBase = Join-Path (Split-Path -Parent $portalSkillsRoot) 'skill-backups'
    $portalBackupBase = [IO.Path]::GetFullPath($portalBackupBase)
    if ($portalBackupBase -eq $portalSkillsRoot -or $portalBackupBase.StartsWith($portalSkillsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Backup directory must be outside SkillsDirectory.'
    }
    $portalBackupRoot = Join-Path $portalBackupBase ('narae-gyomu-work-portal-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    if (Test-Path -LiteralPath $portalBackupRoot) { throw 'Backup path already exists.' }
    New-Item -ItemType Directory -Path $portalBackupRoot -Force | Out-Null
    # Complete every backup before changing any existing skill.
    foreach ($portalJob in $portalChanged) {
        Copy-Item -LiteralPath $portalJob.Target -Destination (Join-Path $portalBackupRoot $portalJob.Name) -Recurse
    }
    Write-Output "Backup: $portalBackupRoot"
}

foreach ($portalJob in $portalJobs) {
    if ($portalJob.Same) { Write-Output "Unchanged: $($portalJob.Name)"; continue }
    New-Item -ItemType Directory -Path $portalJob.Target -Force | Out-Null
    foreach ($portalFile in (Get-PackFiles $portalJob.Source)) {
        $portalRelative = $portalFile.FullName.Substring($portalJob.Source.Length + 1)
        $portalDestination = Join-Path $portalJob.Target $portalRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $portalDestination) -Force | Out-Null
        Copy-Item -LiteralPath $portalFile.FullName -Destination $portalDestination -Force
    }
    Write-Output "Installed: $($portalJob.Name)"
}
Write-Output 'Skill files installed. Python dependencies, browser connection, and personal local settings are configured separately.'
