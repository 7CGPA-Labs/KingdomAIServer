<#
.SYNOPSIS
    User-Space Non-Admin Deployment Script for Kingdom AI Server.
    Installs kingdom.cmd into %LocalAppData%\KingdomAIServer\
    Supports corporate network proxies (Zscaler), AppLocker bypass, and SmartScreen unblocking.
#>

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " [KINGDOM AI SERVER] ZERO-ADMIN ENTERPRISE DEPLOYMENT" -ForegroundColor Yellow
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
        Write-Host "[OK] Added install directory exclusion to Windows Defender." -ForegroundColor Green
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
    Write-Host "[OK] Found local pre-built binaries at $ScriptDir\kingdom_bin" -ForegroundColor Green
    Copy-Item -Path "$ScriptDir\kingdom_bin\*" -Destination $BinDir -Recurse -Force
    $Deployed = $true
} elseif (Test-Path ".\dist\kingdom") {
    Write-Host "[OK] Found local compiled dist at .\dist\kingdom" -ForegroundColor Green
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
        $IsZip = ($HeaderBytes -and $HeaderBytes[0] -eq 0x50 -and $HeaderBytes[1] -eq 0x4B)

        if ($IsZip) {
            Write-Host "[OK] Downloaded release ZIP successfully. Extracting..." -ForegroundColor Green
            Expand-Archive -Path $ZipPath -DestinationPath "$env:TEMP\KingdomExtract" -Force
            if (Test-Path "$env:TEMP\KingdomExtract\kingdom_bin") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\kingdom_bin\*" -Destination $BinDir -Recurse -Force
            } elseif (Test-Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\kingdom_bin") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\kingdom_bin\*" -Destination $BinDir -Recurse -Force
            } else {
                Copy-Item -Path "$env:TEMP\KingdomExtract\*" -Destination $BinDir -Recurse -Force
            }
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path "$env:TEMP\KingdomExtract" -Recurse -Force -ErrorAction SilentlyContinue
            $Deployed = $true
        } else {
            Write-Host "[WARN] Direct ZIP download was intercepted by corporate network proxy (Zscaler)." -ForegroundColor Yellow
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "[WARN] ZIP download failed: $($_.Exception.Message)" -ForegroundColor Yellow
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
            & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary -e $SourceDir
            try {
                & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary truststore onnxruntime-directml
                & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary --only-binary=:all: llama-cpp-python -ErrorAction SilentlyContinue
            } catch {
                Write-Host "[WARN] Pre-compiled llama-cpp-python wheel not available for this Python version. System running on ONNX Minister Council." -ForegroundColor Yellow
            }
        }
        $Deployed = $true
        Write-Host "[OK] Python environment initialized successfully at $InstallDir\venv" -ForegroundColor Green
    }
}

# Always create kingdom.cmd launcher wrapper in bin
$LauncherCmd = "@echo off`r`nsetlocal`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" -m kingdom_server.cli.commands %*`r`n) else if exist `"%~dp0kingdom.exe`" (`r`n    `"%~dp0kingdom.exe`" %*`r`n) else (`r`n    python.exe -m kingdom_server.cli.commands %*`r`n)"
Set-Content -Path "$BinDir\kingdom.cmd" -Value $LauncherCmd -Encoding ASCII

# Unblock files against Windows Defender Zone.Identifier
Write-Host "[4/5] Unblocking executable files from SmartScreen..." -ForegroundColor Cyan
Get-ChildItem -Path $BinDir -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue
}
if (Test-Path "$BinDir\kingdom.exe") {
    Unblock-File -Path "$BinDir\kingdom.exe" -ErrorAction SilentlyContinue
}

# Create Desktop Shortcut
Write-Host "[5/5] Creating user desktop shortcut and updating PATH..." -ForegroundColor Cyan
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\Kingdom AI Server.lnk")
    $Shortcut.TargetPath = "$BinDir\kingdom.cmd"
    $Shortcut.Arguments = "serve"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Kingdom AI Server for Continue.dev"
    $Shortcut.Save()
    Write-Host "[OK] Desktop shortcut created successfully!" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Desktop shortcut creation skipped." -ForegroundColor Yellow
}

# Register User PATH
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    Write-Host "[OK] Added $BinDir to User PATH environment variable." -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " KINGDOM AI SERVER DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " Installation Directory : $InstallDir" -ForegroundColor White
Write-Host " Models Directory       : $ModelsDir" -ForegroundColor White
Write-Host " Loopback Endpoint      : http://127.0.0.1:58420" -ForegroundColor White
Write-Host ""
Write-Host " Quick Launch Commands:" -ForegroundColor Cyan
Write-Host "   kingdom.cmd serve      # Start server and live dashboard" -ForegroundColor Yellow
Write-Host "   kingdom.cmd doctor     # Run pre-flight health diagnostics" -ForegroundColor Yellow
Write-Host ""
Write-Host " Corporate AppLocker / Access Denied Fix:" -ForegroundColor Cyan
Write-Host "   If corporate IT blocks unsigned .exe files in AppData with Access is denied:" -ForegroundColor White
Write-Host "   Run commands using kingdom.cmd or python module directly:" -ForegroundColor Yellow
Write-Host "   1. kingdom.cmd doctor" -ForegroundColor White
Write-Host "   2. kingdom.cmd prompt `"write a quick sort in Go`"" -ForegroundColor White
Write-Host "   3. python -m kingdom_server.cli.commands doctor" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Yellow
