[CmdletBinding()]
param(
    [ValidateSet('Register', 'Status', 'ReadForBrowser')]
    [string]$Action = 'Status',
    [string]$Path = (Join-Path ([System.Environment]::GetFolderPath('LocalApplicationData')) 'Aiedue\GyomuNarae\neis-edufine.credentials.clixml'),
    [string]$Region,
    [ValidateSet('HardDisk', 'Removable')]
    [string]$StorageType,
    [string]$CertificatePath,
    [string]$CertificateName,
    [string]$StorageName,
    [string]$DiskLabel,
    [string]$DiskDrive,
    [System.Security.SecureString]$Password,
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if ([System.Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'This profile store requires Windows DPAPI.' }
# Use this PowerShell installation's modules even when launched from another runtime.
foreach ($module in @('Microsoft.PowerShell.Security', 'Microsoft.PowerShell.Management', 'Microsoft.PowerShell.Utility')) {
    Import-Module (Join-Path $PSHOME "Modules\$module") -ErrorAction Stop
}
$Path = [System.IO.Path]::GetFullPath($Path)

function Assert-CertificateProfile($Profile) {
    if ($Profile.version -ne 1) { throw 'Unsupported certificate profile version.' }
    foreach ($field in @('region', 'storage_type', 'certificate_path', 'certificate_name')) {
        if ([string]::IsNullOrWhiteSpace([string]$Profile.$field)) {
            throw "Missing certificate profile field: $field"
        }
    }
    if ($Profile.storage_type -notin @('HardDisk', 'Removable')) { throw 'Invalid storage type.' }
    if (-not [System.IO.Path]::IsPathRooted($Profile.certificate_path)) { throw 'Use an absolute certificate path.' }
    if ($Profile.storage_type -eq 'Removable' -and
        [string]::IsNullOrWhiteSpace([string]$Profile.disk_label) -and
        [string]::IsNullOrWhiteSpace([string]$Profile.disk_drive)) {
        throw 'Removable storage requires a disk label or drive.'
    }
    if ($Profile.password -isnot [System.Security.SecureString] -or $Profile.password.Length -eq 0) {
        throw 'A nonempty DPAPI-protected password is required.'
    }
}

function Set-PrivateFileAcl([string]$FilePath) {
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $acl = Get-Acl -LiteralPath $FilePath
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($oldRule in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($oldRule) }
    foreach ($sid in @($currentSid, $systemSid)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    if ($PSVersionTable.PSEdition -eq 'Desktop') {
        [System.IO.File]::SetAccessControl($FilePath, $acl)
    } else {
        [System.IO.FileSystemAclExtensions]::SetAccessControl([System.IO.FileInfo]::new($FilePath), $acl)
    }
}

if ($Action -eq 'Register') {
    if ((Test-Path -LiteralPath $Path) -and -not $Replace) {
        throw 'A profile already exists. Use -Replace only for an intended update.'
    }
    $profile = [pscustomobject]@{
        version = 1
        region = $Region
        storage_type = $StorageType
        certificate_path = $CertificatePath
        certificate_name = $CertificateName
        storage_name = $StorageName
        disk_label = $DiskLabel
        disk_drive = $DiskDrive
        password = $Password
    }
    # Validate metadata before asking the user for the secret.
    if (-not $Password) { $profile.password = ConvertTo-SecureString 'validation-only' -AsPlainText -Force }
    Assert-CertificateProfile $profile
    if (-not $Password) { $profile.password = Read-Host 'Certificate password (local input only)' -AsSecureString }
    Assert-CertificateProfile $profile
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }
    # Protect an empty file before exporting any personal metadata.
    if (-not (Test-Path -LiteralPath $Path)) { [System.IO.File]::WriteAllText($Path, '') }
    Set-PrivateFileAcl $Path
    $profile | Export-Clixml -LiteralPath $Path -Depth 4 -Encoding UTF8
    '{"registered":true,"password_protection":"Windows DPAPI CurrentUser","file_acl":"current user and SYSTEM"}'
    exit 0
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    if ($Action -eq 'Status') { '{"exists":false,"valid":false}'; exit 0 }
    throw 'Certificate profile not found. Register it locally first.'
}
$profile = Import-Clixml -LiteralPath $Path
Assert-CertificateProfile $profile

if ($Action -eq 'Status') {
    [pscustomobject]@{
        exists = $true
        valid = $true
        certificate_path_exists = (Test-Path -LiteralPath $profile.certificate_path)
    } | ConvertTo-Json -Compress
    exit 0
}

# PRIVATE IPC ONLY: capture stdout in the browser controller's local memory.
# Never run ReadForBrowser as a visible terminal command or print its result.
$pointer = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($profile.password)
try {
    [pscustomobject]@{
        region = $profile.region
        storage_type = $profile.storage_type
        certificate_path = $profile.certificate_path
        certificate_name = $profile.certificate_name
        storage_name = $profile.storage_name
        disk_label = $profile.disk_label
        disk_drive = $profile.disk_drive
        password = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } | ConvertTo-Json -Compress
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}
