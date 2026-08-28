$ErrorActionPreference = "Stop"
$ArisProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ArisProjectRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "ARIS virtual environment is missing. Run scripts\setup.ps1 first."
}

& ".venv\Scripts\python.exe" -m aris
