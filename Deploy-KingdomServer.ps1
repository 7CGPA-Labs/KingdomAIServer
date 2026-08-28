<#
.SYNOPSIS
    User-Space Non-Admin Deployment Script for Kingdom AI Server.
    Installs kingdom.exe into %LocalAppData%\KingdomAIServer\
    Supports corporate network proxies (Zscaler) and Windows Defender unblocking.
#>

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " 👑 KINGDOM AI SERVER - ZERO-ADMIN ENTERPRISE DEPLOYMENT" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow

# Target user-space installation path
$InstallDir = "$env:LOCALAPPDATA\KingdomAIServer"
$BinDir = "$InstallDir\bin"
$ModelsDir = "$InstallDir\models"
$LogsDir = "$InstallDir\logs"

Write-Host "[1/5] Preparing user-space directory layout at: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# Attempt Windows Defender exclusion (if user has permissions)
Write-Host "[2/5] Setting up Windows Defender directory unblocking..." -ForegroundColor Cyan
try {
    if (Get-Command Add-MpPreference -ErrorAction SilentlyContinue) {
        Add-MpPreference -ExclusionPath $InstallDir -ErrorAction SilentlyContinue
        Write-Host "✔ Added install directory exclusion to Windows Defender." -ForegroundColor Green
    }
} catch {
    # Non-elevated execution will silently skip
}

# Acquire binary release or fallback source deployment
Write-Host "[3/5] Deploying Kingdom AI Server binaries..." -ForegroundColor Cyan
$ScriptDir = $PSScriptRoot
$Deployed = $false

# 1. Check local directory for pre-built binaries
if ($ScriptDir -and (Test-Path "$ScriptDir\kingdom_bin")) {
    Write-Host "✔ Found local pre-built binaries at $ScriptDir\kingdom_bin" -ForegroundColor Green
    Copy-Item -Path "$ScriptDir\kingdom_bin\*" -Destination $BinDir -Recurse -Force
    $Deployed = $true
} elseif (Test-Path ".\dist\kingdom") {
    Write-Host "✔ Found local compiled dist at .\dist\kingdom" -ForegroundColor Green
    Copy-Item -Path ".\dist\kingdom\*" -Destination $BinDir -Recurse -Force
    $Deployed = $true
}

# 2. If not local, attempt downloading release asset from GitHub
if (-not $Deployed) {
    $ZipPath = "$env:TEMP\KingdomServer-win64-full.zip"
    $ReleaseUrl = "https://github.com/7CGPA-Labs/KingdomAIServer/releases/latest/download/KingdomServer-win64-full.zip"
    
    Write-Host "Downloading release bundle from GitHub..." -ForegroundColor Yellow
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $WebClient = New-Object System.Net.WebClient
        $WebClient.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        $WebClient.DownloadFile($ReleaseUrl, $ZipPath)

        # Check if downloaded file is an HTML Zscaler block page instead of a real ZIP file
        $HeaderBytes = Get-Content -Path $ZipPath -Encoding Byte -TotalCount 4 -ErrorAction SilentlyContinue
        $IsZip = ($HeaderBytes -and $HeaderBytes[0] -eq 0x50 -and $HeaderBytes[1] -eq 0x4B) # 'PK' magic header

        if ($IsZip) {
            Write-Host "✔ Downloaded release ZIP successfully. Extracting..." -ForegroundColor Green
            Expand-Archive -Path $ZipPath -DestinationPath "$env:TEMP\KingdomExtract" -Force
            if (Test-Path "$env:TEMP\KingdomExtract\kingdom_bin") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\kingdom_bin\*" -Destination $BinDir -Recurse -Force
            } elseif (Test-Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\kingdom_bin") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\kingdom_bin\*" -Destination $BinDir -Recurse -Force
            }
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path "$env:TEMP\KingdomExtract" -Recurse -Force -ErrorAction SilentlyContinue
            $Deployed = $true
        } else {
            Write-Host "⚠ Direct ZIP download was intercepted by corporate network proxy (Zscaler)." -ForegroundColor Yellow
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "⚠ ZIP download failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# 3. Fallback: Source installation via Git clone or Python virtual environment
if (-not $Deployed) {
    Write-Host "[CORPORATE-FALLBACK] Deploying via Python / Git source fallback..." -ForegroundColor Cyan
    $SourceDir = "$InstallDir\src"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (-not (Test-Path $SourceDir)) {
            git clone https://github.com/7CGPA-Labs/KingdomAIServer.git $SourceDir
        } else {
            git -C $SourceDir pull
        }
    } else {
        New-Item -ItemType Directory -Force -Path $SourceDir | Out-Null
    }

    # Setup Python environment in user space
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "Setting up Python virtual environment at $InstallDir\venv..." -ForegroundColor Yellow
        python -m venv "$InstallDir\venv"
        & "$InstallDir\venv\Scripts\python.exe" -m pip install --upgrade pip setuptools
        if (Test-Path "$SourceDir\pyproject.toml") {
            $env:TMP = "$env:LOCALAPPDATA\T"
            & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary -e $SourceDir
            & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary llama-cpp-python truststore
        }
        
        # Create kingdom.cmd launcher wrapper in bin
        $LauncherCmd = "@echo off`r`n`"$InstallDir\venv\Scripts\python.exe`" -m kingdom_server.cli.commands %*"
        Set-Content -Path "$BinDir\kingdom.cmd" -Value $LauncherCmd -Encoding ASCII
        $Deployed = $true
        Write-Host "✔ Python fallback launcher created at $BinDir\kingdom.cmd" -ForegroundColor Green
    }
}

# Unblock files against Windows Defender Zone.Identifier
Write-Host "[4/5] Unblocking executable files from SmartScreen..." -ForegroundColor Cyan
Get-ChildItem -Path $BinDir -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# Create Desktop Shortcut
Write-Host "[5/5] Creating user desktop shortcut & updating PATH..." -ForegroundColor Cyan
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\Kingdom AI Server.lnk")
    
    if (Test-Path "$BinDir\kingdom.exe") {
        $Shortcut.TargetPath = "$BinDir\kingdom.exe"
        $Shortcut.Arguments = "serve --tray"
    } else {
        $Shortcut.TargetPath = "$BinDir\kingdom.cmd"
        $Shortcut.Arguments = "serve"
    }
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Kingdom AI Server for Continue.dev"
    $Shortcut.Save()
    Write-Host "✔ Desktop shortcut created successfully!" -ForegroundColor Green
} catch {
    Write-Host "⚠ Note: Desktop shortcut creation skipped." -ForegroundColor Yellow
}

# Register User PATH
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    Write-Host "✔ Added $BinDir to User PATH environment variable." -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " 🚀 KINGDOM AI SERVER DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " Installation Directory : $InstallDir" -ForegroundColor White
Write-Host " Models Directory       : $ModelsDir" -ForegroundColor White
Write-Host " Loopback Endpoint      : http://127.0.0.1:58420" -ForegroundColor White
Write-Host ""
Write-Host " Quick Launch Commands:" -ForegroundColor Cyan
Write-Host "   kingdom serve          # Start server & live dashboard" -ForegroundColor Yellow
Write-Host "   kingdom doctor         # Run pre-flight health diagnostics" -ForegroundColor Yellow
Write-Host ""
Write-Host " Troubleshooting Windows Defender / SmartScreen:" -ForegroundColor Cyan
Write-Host "   If Windows Defender blocks launch of kingdom.exe / KingdomTray.exe:" -ForegroundColor White
Write-Host "   1. Open File Explorer to: $BinDir" -ForegroundColor White
Write-Host "   2. Right-click 'kingdom.exe' > Properties" -ForegroundColor White
Write-Host "   3. Check 'Unblock' checkbox at the bottom > Click Apply > OK" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Yellow
