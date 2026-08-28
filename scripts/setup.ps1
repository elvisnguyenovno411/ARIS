$ErrorActionPreference = "Stop"
$ArisProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ArisProjectRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -e ".[vision,voice,mesh,dev]"
Write-Host "ARIS setup complete. Run scripts\run.ps1 to start the app."
