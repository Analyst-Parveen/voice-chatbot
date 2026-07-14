# Starts the Voice AI frontend (Next.js production server on port 3000).
# Run frontend-setup.ps1 once first (installs deps + builds); then start here.
# For local development you can use 'npm run dev' instead.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$AppDir = if ($env:APP_DIR) { $env:APP_DIR } else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
$FrontendDir = Join-Path $AppDir "frontend"

Set-Location $FrontendDir
npm run start
