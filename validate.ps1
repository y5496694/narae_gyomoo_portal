[CmdletBinding()]
param(
    [string]$Python = 'python',
    [string]$Node = 'node'
)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    & $Python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    & $Node tests/test_actions.cjs
    if ($LASTEXITCODE -ne 0) { throw 'JavaScript tests failed.' }
    & $Python -X utf8 skills/wxs-cli/scripts/wxs_cli.py doctor
    if ($LASTEXITCODE -ne 0) { throw 'WXS environment check failed.' }
    Write-Output 'Offline validation passed. Live login, document changes, and server saves were not run.'
} finally {
    Pop-Location
}
