# Starts the Voice AI backend (FastAPI via uvicorn).
# Used by the 'voiceai-backend' scheduled task (auto-start on boot) and can also
# be run by hand. Uses the venv's python by absolute path, so it works from any
# folder and under the SYSTEM account (no PATH dependency).
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$AppDir = if ($env:APP_DIR) { $env:APP_DIR } else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
$BackendDir = Join-Path $AppDir "backend"
$PythonExe  = Join-Path $BackendDir "venv\Scripts\python.exe"

Set-Location $BackendDir
& $PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
