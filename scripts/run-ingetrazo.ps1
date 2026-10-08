<#
.SYNOPSIS
    One-click local run: link every extension in this repo into a local
    IngeTrazo checkout, then launch IngeTrazo so you can try them out.

.DESCRIPTION
    Wraps scripts\dev-link.ps1 for every extension under this repo's
    extensions\ folder, then launches the target IngeTrazo checkout's
    main.py. Intended to back the app's "Run" button so the current
    session's extensions are installed and immediately testable.

.PARAMETER IngetrazoPath
    Path to a local clone of https://github.com/kagehak/ingetrazo. Defaults
    to $env:INGETRAZO_PATH, falling back to a hardcoded default below.

.EXAMPLE
    scripts\run-ingetrazo.ps1
    scripts\run-ingetrazo.ps1 -IngetrazoPath D:\code\ingetrazo
#>
param(
    [string]$IngetrazoPath = $(if ($env:INGETRAZO_PATH) { $env:INGETRAZO_PATH } else { 'C:\Users\kageh\Projects\ingetrazo' })
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path.TrimEnd('\')
$extensionsDir = Join-Path $repoRoot 'extensions'

if (-not (Test-Path -LiteralPath (Join-Path $IngetrazoPath 'main.py'))) {
    throw ("Could not find 'main.py' under '$IngetrazoPath'. Clone " +
           "https://github.com/kagehak/ingetrazo locally and either set " +
           "`$env:INGETRAZO_PATH or pass -IngetrazoPath.")
}

# One-time venv + dependency setup, matching docs\developing-and-testing.md.
$venvPython = Join-Path $IngetrazoPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "No IngeTrazo venv found; creating one (first run only)..."
    python -m venv (Join-Path $IngetrazoPath '.venv')
    $requirements = Join-Path $IngetrazoPath 'requirements.txt'
    if (Test-Path -LiteralPath $requirements) {
        & $venvPython -m pip install -r $requirements
    }
}

# Link every extension in this repo so they're all installed for the run.
Get-ChildItem -LiteralPath $extensionsDir | ForEach-Object {
    $extName = $_.BaseName
    Write-Host "Linking extension: $extName"
    & (Join-Path $repoRoot 'scripts\dev-link.ps1') -Name $extName
}

Write-Host "Launching IngeTrazo from $IngetrazoPath ..."
Push-Location $IngetrazoPath
try {
    & $venvPython main.py
} finally {
    Pop-Location
}
