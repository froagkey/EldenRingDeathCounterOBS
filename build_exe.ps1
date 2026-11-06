[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venv = Join-Path $root '.venv-build'
$python = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    py -m venv $venv
}

if (-not $SkipDependencyInstall) {
    & $python -m pip install --upgrade pip
    & $python -m pip install --editable "$root[build]"
}

& $python -m PyInstaller --clean --noconfirm `
    (Join-Path $root 'EldenRingDeathCounter.spec')

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$executable = Join-Path $root 'dist\EldenRingDeathCounter.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    throw "The build completed without producing $executable."
}

Write-Host ""
Write-Host "Built: $executable"
