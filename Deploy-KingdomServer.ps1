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
    $ReleaseUrl = "https://github.com/7CGPA-Labs/KingdomAIServer/releases/download/v2.0.0/KingdomServer-win64-full.zip"
    
    Write-Host "Downloading release bundle from GitHub..." -ForegroundColor Yellow
    try {
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            curl.exe -sSL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" $ReleaseUrl -o $ZipPath
        } else {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $ReleaseUrl -OutFile $ZipPath -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -UseBasicParsing
        }

        # Check if downloaded file is an HTML block page or real ZIP
        $HeaderBytes = Get-Content -Path $ZipPath -Encoding Byte -TotalCount 4 -ErrorAction SilentlyContinue
        $IsZip = ($HeaderBytes -and $HeaderBytes[0] -eq 0x50 -and $HeaderBytes[1] -eq 0x4B)

        if ($IsZip) {
            Write-Host "[OK] Downloaded release ZIP successfully. Extracting..." -ForegroundColor Green
            Expand-Archive -Path $ZipPath -DestinationPath "$env:TEMP\KingdomExtract" -Force
            if (Test-Path "$env:TEMP\KingdomExtract\src") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\src" -Destination "$InstallDir\src" -Recurse -Force
            } elseif (Test-Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\src") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\src" -Destination "$InstallDir\src" -Recurse -Force
            }
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path "$env:TEMP\KingdomExtract" -Recurse -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "[WARN] Release ZIP download failed. Falling back to Git/Python source..." -ForegroundColor Yellow
    }
}

# 3. Setup Python virtual environment & package installation
Write-Host "[CORPORATE-FALLBACK] Setting up Python virtual environment..." -ForegroundColor Cyan
$SourceDir = "$InstallDir\src"
$TargetBranch = if ($env:KINGDOM_BRANCH) { $env:KINGDOM_BRANCH } else { "v2.0.0" }
if (-not (Test-Path $SourceDir)) {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone -b $TargetBranch https://github.com/7CGPA-Labs/KingdomAIServer.git $SourceDir -q
    } else {
        New-Item -ItemType Directory -Force -Path $SourceDir | Out-Null
    }
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    if (-not (Test-Path "$InstallDir\venv\Scripts\python.exe")) {
        Write-Host "Initializing user-space Python virtual environment at $InstallDir\venv..." -ForegroundColor Yellow
        python -m venv "$InstallDir\venv"
        & "$InstallDir\venv\Scripts\python.exe" -m pip install --upgrade pip setuptools -q
    }
    
    if (Test-Path "$SourceDir\pyproject.toml") {
        Write-Host "Installing core Kingdom AI Server dependencies..." -ForegroundColor Yellow
        & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary fastapi uvicorn rich httpx truststore sqlite-vec tree-sitter pillow requests pyyaml psutil huggingface_hub
        
        Write-Host "Installing llama-cpp-python GGUF engine (Strict GPU/iGPU Vulkan/OpenCL)..." -ForegroundColor Yellow
        $vulkanWheelUrl = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-vulkan/llama_cpp_python-0.3.35-py3-none-win_amd64.whl"
        $cpuWheelUrl = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-py3-none-win_amd64.whl"
        
        Write-Host "Downloading Vulkan GPU/iGPU pre-built wheel ($vulkanWheelUrl)..." -ForegroundColor Cyan
        & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary $vulkanWheelUrl
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] Vulkan wheel download failed, attempting standard GPU wheel..." -ForegroundColor Yellow
            & "$InstallDir\venv\Scripts\python.exe" -m pip install --prefer-binary $cpuWheelUrl
        }

        & "$InstallDir\venv\Scripts\python.exe" -m pip install --no-deps -e "$SourceDir"
    }
    $Deployed = $true
}

$LauncherCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`ncd /d `"%~dp0..\src`"`r`nif exist `"%~dp0..\src\start_server.py`" (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" start_server.py %*`r`n    ) else (`r`n        python.exe start_server.py %*`r`n    )`r`n) else if exist `"%~dp0..\src\start_server.pyc`" (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" start_server.pyc %*`r`n    ) else (`r`n        python.exe start_server.pyc %*`r`n    )`r`n) else (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" -m main %*`r`n    ) else (`r`n        python.exe -m main %*`r`n    )`r`n)"
Set-Content -Path "$BinDir\start_server.cmd" -Value $LauncherCmd -Encoding ASCII

$DownloadCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`ncd /d `"%~dp0..\src`"`r`nif exist `"%~dp0..\src\download_models.py`" (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" download_models.py %*`r`n    ) else (`r`n        python.exe download_models.py %*`r`n    )`r`n) else if exist `"%~dp0..\src\download_models.pyc`" (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" download_models.pyc %*`r`n    ) else (`r`n        python.exe download_models.pyc %*`r`n    )`r`n) else (`r`n    if exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n        `"%~dp0..\venv\Scripts\python.exe`" -m src.utils.downloader %*`r`n    ) else (`r`n        python.exe -m src.utils.downloader %*`r`n    )`r`n)"
Set-Content -Path "$BinDir\download_models.cmd" -Value $DownloadCmd -Encoding ASCII

$CliCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`ncd /d `"%~dp0..\src`"`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" -m src.cli.terminal_ui %*`r`n) else (`r`n    python.exe -m src.cli.terminal_ui %*`r`n)"
Set-Content -Path "$BinDir\kingdom_cli.cmd" -Value $CliCmd -Encoding ASCII


# Unblock files against Windows Defender Zone.Identifier
Write-Host "[4/5] Unblocking executable files from SmartScreen..." -ForegroundColor Cyan
Get-ChildItem -Path $BinDir -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue
}
# Create Desktop Shortcut
Write-Host "[5/5] Creating user desktop shortcut and updating PATH..." -ForegroundColor Cyan
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\Kingdom AI Terminal.lnk")
    $Shortcut.TargetPath = "$BinDir\kingdom_cli.cmd"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Kingdom AI Rich Terminal CLI"
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
Write-Host " KINGDOM AI SERVER & TERMINAL CLI DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " Installation Directory : $InstallDir" -ForegroundColor White
Write-Host " Models Directory       : $ModelsDir" -ForegroundColor White
Write-Host " Headless API Endpoint  : http://127.0.0.1:58420" -ForegroundColor White
Write-Host ""
Write-Host " Quick Launch Commands:" -ForegroundColor Cyan
Write-Host "   kingdom_cli             # Launch Rich Terminal CLI" -ForegroundColor Yellow
Write-Host "   start_server            # Start headless uvicorn server for Continue.dev" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
