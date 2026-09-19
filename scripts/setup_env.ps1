# Kingdom AI Server V2 Environment Setup Script (Windows DirectML & AVX2)

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 👑 KINGDOM AI SERVER V2 ENVIRONMENT SETUP" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$VENV_DIR = "venv"
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating Python virtual environment in .\venv..." -ForegroundColor Yellow
    python -m venv $VENV_DIR
}

$PYTHON = ".\venv\Scripts\python.exe"
$PIP = ".\venv\Scripts\pip.exe"

Write-Host "Upgrading pip and setuptools..." -ForegroundColor Yellow
& $PIP install --upgrade pip setuptools wheel

Write-Host "Installing Kingdom AI Server V2 dependencies from requirements.txt..." -ForegroundColor Yellow
& $PIP install -r requirements.txt

Write-Host "Verifying Stage 1 dependencies..." -ForegroundColor Green
& $PYTHON -c "import tree_sitter; import truststore; import yaml; import fastapi; print('✅ Stage 1 Core Dependencies Verified Successfully')"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " Environment Setup Complete." -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
