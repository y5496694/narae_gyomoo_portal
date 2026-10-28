[CmdletBinding()]
param([string]$Python='python', [string]$RuntimeDirectory)
$ErrorActionPreference = 'Stop'
if (-not $RuntimeDirectory) {
    $RuntimeDirectory = Join-Path $env:LOCALAPPDATA 'NaraeGyomuPortal\attachment-readers\0.3.0'
}
$runtime = [IO.Path]::GetFullPath($RuntimeDirectory)
$readerPython = Join-Path $runtime 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $readerPython)) {
    & $Python -m venv $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated attachment-reader environment.' }
}
& $readerPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Reader dependencies could not be installed.' }
& $readerPython (Join-Path $PSScriptRoot '..\attachment_reader.py') --doctor
if ($LASTEXITCODE -ne 0) { throw 'Reader environment check failed.' }
@{ python=$readerPython; isolated=$true; wxs_login='not performed' } | ConvertTo-Json

& $readerPython (Join-Path $PSScriptRoot 'narae_hangul_office\narae.py') doctor
if ($LASTEXITCODE -ne 0) { throw 'Install Narae Hangul Office with its installer before reading HWP/HWPX.' }
