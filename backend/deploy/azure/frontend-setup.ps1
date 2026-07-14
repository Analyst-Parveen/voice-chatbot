# One-time FRONTEND setup on a Windows Server / Windows VM - NO DOCKER.
#
#   cd D:\voice-ai-assistant
#   powershell -ExecutionPolicy Bypass -File backend\deploy\azure\frontend-setup.ps1
#
# Prereq: set frontend\.env.local first (NEXT_PUBLIC_API_BASE_URL and
# NEXT_PUBLIC_WS_BASE_URL) - localhost for same-box, or the VM IP/domain for
# remote access.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$AppDir = if ($env:APP_DIR) { $env:APP_DIR } else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
$FrontendDir = Join-Path $AppDir "frontend"
$EnvFile = Join-Path $FrontendDir ".env.local"

if (-not (Test-Path $EnvFile)) {
    Write-Error "frontend\.env.local not found. Create it (NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_WS_BASE_URL) before running this setup."
}

Set-Location $FrontendDir

# ---- [1/2] Node.js ----
Write-Step "[1/2] Node.js ..."
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "  [ok] node $(node -v)"
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "  [install] Node.js LTS ..."
    winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Error "Node.js not found. Install Node 18+ from https://nodejs.org and re-run."
}

# ---- [2/2] Install packages + production build ----
Write-Step "[2/2] npm install + build ..."
npm install
npm run build

Write-Host ""
Write-Host "==> Frontend setup complete." -ForegroundColor Green
Write-Host "    Start (production):  powershell -File backend\deploy\azure\start-frontend.ps1"
Write-Host "    Or dev mode:         npm run dev   (from the frontend folder)"
