# One-time BACKEND setup on a Windows Server / Windows VM — NO DOCKER.
#
#   cd C:\voice-agent
#   powershell -ExecutionPolicy Bypass -File backend\deploy\azure\backend-setup.ps1
#
# Prereqs: copy backend\.env.stub to backend\.env and edit (DB, CORS, etc.)
# Optional: set $env:APP_DIR if the repo is not three levels above this script.

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-DotEnvValue([string]$Key, [string]$EnvFile) {
    if (-not (Test-Path $EnvFile)) { return $null }
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Ensure-Command([string]$Name, [scriptblock]$Install) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        Write-Host "  [ok] $Name already installed"
        return
    }
    Write-Host "  [install] $Name ..."
    & $Install
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Warning "  Could not install $Name automatically — install manually and re-run."
    }
}

function Stop-BackendOnPort8000 {
    try {
        $conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Older Windows / no admin — skip
    }
}

# ---- Paths ----
$AppDir = if ($env:APP_DIR) { $env:APP_DIR } else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
$BackendDir = Join-Path $AppDir "backend"
$EnvFile = Join-Path $BackendDir ".env"
$VenvDir = Join-Path $BackendDir "venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
$DataDir = Join-Path $AppDir "data"

# Make the backend package importable by helper scripts that are run by FILE
# path (e.g. scripts\download_models.py, which does `import app.core.config`).
# Running a script by path only puts the script's OWN folder on sys.path, so
# without this `import app` fails and the Piper voices never download.
$env:PYTHONPATH = $BackendDir

Set-Location $AppDir

if (-not (Test-Path $EnvFile)) {
    Write-Error "backend\.env not found. Create and configure backend\.env (RUN_MODE, LLM/STT/TTS models, DB, CORS) BEFORE running this setup - see backend\deploy\azure\README.md."
}

Write-Host "Voice AI Assistant — Windows backend setup"
Write-Host "App directory: $AppDir"

# ---- [1/7] System tools (winget when available) ----
Write-Step "[1/7] System tools (Python 3.11, Git, ffmpeg, Ollama) ..."
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Ensure-Command "python" { winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements | Out-Null }
    Ensure-Command "git" { winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements | Out-Null }
    Ensure-Command "ffmpeg" { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements | Out-Null }
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host "  [install] Ollama ..."
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements | Out-Null
    } else {
        Write-Host "  [ok] ollama already installed"
    }
} else {
    Write-Warning "winget not found. Install manually: Python 3.11, Git, ffmpeg, Ollama from https://ollama.com/download"
}

# Refresh PATH for current session (common after winget installs)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" `
          + [System.Environment]::GetEnvironmentVariable("Path", "User")

$PyLauncher = $null
foreach ($candidate in @("py -3.11", "python3.11", "python")) {
    $name = $candidate.Split(" ")[0]
    if ($candidate -eq "py -3.11") {
        if (Get-Command py -ErrorAction SilentlyContinue) { $PyLauncher = @("py", "-3.11"); break }
    } elseif (Get-Command $name -ErrorAction SilentlyContinue) {
        $PyLauncher = @($name)
        break
    }
}
if (-not $PyLauncher) {
    Write-Error "Python 3.11+ not found. Install from https://www.python.org/downloads/ and re-run."
}

# ---- [2/7] Ollama model ----
Write-Step "[2/7] Ollama LLM model ..."
$llmModel = Get-DotEnvValue "LLM_MODEL" $EnvFile
if (-not $llmModel -or $llmModel -eq "stub") { $llmModel = "qwen2.5:3b" }

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "  Pulling $llmModel (may take several minutes) ..."
    ollama pull $llmModel
} else {
    Write-Warning "  ollama not in PATH — skip model pull. Install Ollama and run: ollama pull $llmModel"
}

# ---- [3/7] Python venv + dependencies ----
Write-Step "[3/7] Python venv + pip packages (heavy — one time) ..."
Set-Location $BackendDir
if (-not (Test-Path $VenvDir)) {
    & @($PyLauncher + @("-m", "venv", "venv"))
}
& $PipExe install --upgrade pip
& $PipExe install -r requirements.txt

# MSSQL optional extra (Windows usually has ODBC available)
$mssqlDriver = Get-DotEnvValue "DB_BACKEND" $EnvFile
if ($mssqlDriver -eq "mssql") {
    Write-Host "  DB_BACKEND=mssql — ensure 'ODBC Driver 17 for SQL Server' is installed."
}

# ---- [4/7] Model assets: Piper voices + Whisper (STT) + embeddings ----
Write-Step "[4/7] Downloading model assets (Piper voices, Whisper STT, bge-m3 embeddings) ..."
# --piper: TTS voices.  --warm: pre-cache Whisper + the embedding model so the
# first mic/RAG use isn't a slow cold download (real models, never stub).
& $PythonExe (Join-Path $AppDir "scripts\download_models.py") --piper --warm
$PiperDir = Join-Path $AppDir "models\piper"
if ((Test-Path $PiperDir) -and (Get-ChildItem $PiperDir -Filter *.onnx -ErrorAction SilentlyContinue)) {
    Write-Host "  [ok] Piper voices present — voice replies will speak."
} else {
    Write-Warning "  Piper voices missing — voice replies would fall back to text only."
    Write-Host  ("  Retry manually:  `$env:PYTHONPATH='{0}'; & '{1}' scripts\download_models.py --piper" -f $BackendDir, $PythonExe)
}

# ---- [5/7] Database migrations ----
Write-Step "[5/7] Database migrations ..."
& $PythonExe -m alembic upgrade head

# ---- [6/7] Knowledge ingestion ----
Write-Step "[6/7] Knowledge ingestion (embedded Qdrant — stop backend first) ..."
Stop-BackendOnPort8000
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
    Write-Warning "Created empty $DataDir — add company docs and re-run with deploy-backend.ps1 -Ingest"
}
try {
    & $PythonExe -m ingestion.run_ingestion --data-dir $DataDir
} catch {
    Write-Warning "Ingestion skipped or failed (empty data/ is OK for first run): $_"
}

# ---- [7/7] Auto-start at boot (Scheduled Task) ----
Write-Step "[7/7] Register Windows scheduled task 'voiceai-backend' ..."
$StartScript = Join-Path $PSScriptRoot "start-backend.ps1"
$TaskName = "voiceai-backend"
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $StartScript) `
    -WorkingDirectory $AppDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -Principal $Principal -Description "Voice AI FastAPI backend" | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "  Scheduled task registered and started."
} catch {
    Write-Warning "Could not register scheduled task (run PowerShell as Administrator)."
    Write-Host ""
    Write-Host "  Start manually instead:" -ForegroundColor Yellow
    Write-Host ('  powershell -File "{0}"' -f $StartScript)
}

Set-Location $AppDir
Write-Host ""
Write-Host "==> Backend setup complete." -ForegroundColor Green
Write-Host "    Health:  http://localhost:8000/api/health"
Write-Host "    Manual:  powershell -File backend\deploy\azure\start-backend.ps1"
Write-Host "    Task:    Get-ScheduledTask -TaskName voiceai-backend"