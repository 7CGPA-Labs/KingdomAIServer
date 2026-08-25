<#
.SYNOPSIS
    User-Space Non-Admin Deployment Script for Kingdom AI Server.
    Installs kingdom.exe into %LocalAppData%\KingdomAIServer\
#>

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Gold
Write-Host " 👑 KINGDOM AI SERVER - NON-ADMIN USER-SPACE DEPLOYMENT" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Gold

# Target user-space installation path
$InstallDir = "$env:LOCALAPPDATA\KingdomAIServer"
$BinDir = "$InstallDir\bin"
$ModelsDir = "$InstallDir\models"
$LogsDir = "$InstallDir\logs"

Write-Host "[1/4] Preparing user-space directory layout at: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# Copy binary dist files if executing from unpacked release folder
$ScriptDir = $PSScriptRoot
if (Test-Path "$ScriptDir\kingdom_bin") {
    Write-Host "[2/4] Deploying kingdom.exe binary release package..." -ForegroundColor Cyan
    Copy-Item -Path "$ScriptDir\kingdom_bin\*" -Destination $BinDir -Recurse -Force
} else {
    Write-Host "[2/4] Staging deployment directories..." -ForegroundColor Yellow
}

# Create desktop shortcut (no elevation required)
Write-Host "[3/4] Creating user desktop shortcut..." -ForegroundColor Cyan
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\Kingdom AI Server.lnk")
    
    if (Test-Path "$BinDir\kingdom.exe") {
        $Shortcut.TargetPath = "$BinDir\kingdom.exe"
        $Shortcut.Arguments = "serve --tray"
    } else {
        $Shortcut.TargetPath = "powershell.exe"
        $Shortcut.Arguments = "-NoExit -Command kingdom serve"
    }
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Kingdom AI Server for Continue.dev"
    $Shortcut.Save()
    Write-Host "✔ Shortcut created successfully on Desktop!" -ForegroundColor Green
} catch {
    Write-Host "⚠ Note: Shortcut creation skipped ($($_.Exception.Message))" -ForegroundColor Yellow
}

# Add user PATH if not present
Write-Host "[4/4] Registering User Environment PATH..." -ForegroundColor Cyan
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    Write-Host "✔ Added $BinDir to User PATH environment variable." -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Gold
Write-Host " 🚀 KINGDOM AI SERVER DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Gold
Write-Host " Installation Directory : $InstallDir" -ForegroundColor White
Write-Host " Models Folder          : $ModelsDir" -ForegroundColor White
Write-Host " Server Address         : http://127.0.0.1:58420" -ForegroundColor White
Write-Host ""
Write-Host " To start the server, run in PowerShell:" -ForegroundColor Cyan
Write-Host "   kingdom serve" -ForegroundColor Yellow
Write-Host ""
Write-Host " To run pre-flight health diagnostics:" -ForegroundColor Cyan
Write-Host "   kingdom doctor" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Gold
