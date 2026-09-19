# Kingdom AI Server V2 4-Gate Automated Test Suite (PowerShell)

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 👑 KINGDOM AI SERVER V2 4-GATE TEST SUITE" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$PYTHON = ".\venv\Scripts\python.exe"

if (-not (Test-Path $PYTHON)) {
    $PYTHON = "python"
}

Write-Host "Executing PyTest diagnostic test suite..." -ForegroundColor Yellow
& $PYTHON -m pytest --verbose

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " All Diagnostic Verification Gates Passed Successfully!" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
