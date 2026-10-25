# Starts VeriGate locally WITHOUT Docker:
#   backend  -> http://localhost:8000
#   frontend -> http://localhost:5173
# First run installs the Python venv and npm dependencies automatically.
$ErrorActionPreference = "Continue"

$root     = Split-Path -Parent $PSScriptRoot          # bundle root
$backend  = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvDir  = Join-Path $backend "venv"
$venvPy   = Join-Path $venvDir "Scripts\python.exe"

Write-Host "[dev] VeriGate local startup" -ForegroundColor Cyan

# ---------------------------------------------------------------- backend --
if (-not (Test-Path $venvPy)) {
    Write-Host "[dev] creating Python venv..." -ForegroundColor Cyan
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += , @("py", "-3.12")   # recommended (matches requirements.txt)
        $candidates += , @("py", "-3.13")
        $candidates += , @("py", "-3.11")
        $candidates += , @("py", "-3.10")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += , @("python")
    }
    if ($candidates.Count -eq 0) {
        Write-Host "[dev] No Python found. Install Python 3.12 from https://python.org" -ForegroundColor Red
        exit 1
    }
    foreach ($c in $candidates) {
        $extra = @()
        if ($c.Count -gt 1) { $extra = $c[1..($c.Count - 1)] }
        & $c[0] @extra -m venv $venvDir 2>$null | Out-Null
        if (Test-Path $venvPy) { break }
    }
    if (-not (Test-Path $venvPy)) {
        Write-Host "[dev] Failed to create the virtualenv. Is Python 3.11-3.13 installed?" -ForegroundColor Red
        exit 1
    }
}

# install dependencies only when they are missing
& $venvPy -c "import fastapi, uvicorn" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[dev] installing backend dependencies (first run only, ~1-2 min)..." -ForegroundColor Cyan
    & $venvPy -m pip install --upgrade pip 2>$null | Out-Null
    & $venvPy -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[dev] pip install failed." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------- frontend --
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "[dev] npm not found. Install Node.js 20+ from https://nodejs.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "[dev] installing frontend dependencies (first run only)..." -ForegroundColor Cyan
    Push-Location $frontend
    npm install --no-fund --no-audit
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[dev] npm install failed." -ForegroundColor Red
        exit 1
    }
}

# --------------------------------------------------------------- launch ----
Write-Host "[dev] starting backend on http://localhost:8000 ..." -ForegroundColor Green
$backendCmd = "Set-Location '$backend'; & '$venvPy' -m uvicorn main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "[dev] starting frontend on http://localhost:5173 ..." -ForegroundColor Green
$frontendCmd = "Set-Location '$frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Start-Sleep -Seconds 4
Write-Host ""
Write-Host "[dev] Opening the app in a few seconds. First boot seeds ~30 applications (~30s)." -ForegroundColor Yellow
Write-Host "[dev] Sign in: officer1/officer123 | reviewer1/reviewer123 | auditor1/auditor123"
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
