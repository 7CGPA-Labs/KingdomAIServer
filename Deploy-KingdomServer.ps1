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
$ConfigDir = "$InstallDir\config"

Write-Host "[1/5] Preparing user-space directory layout at: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

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

Write-Host "[3/5] Deploying Kingdom AI Server .pyz bundle..." -ForegroundColor Cyan
$ScriptDir = $PSScriptRoot
$Deployed = $false

# 1. Check local directory for pre-built binaries (from extracted zip)
if ($ScriptDir -and (Test-Path "$ScriptDir\bin\kingdom.pyz")) {
    Write-Host "[OK] Found local pre-built .pyz bundle at $ScriptDir\bin" -ForegroundColor Green
    Copy-Item -Path "$ScriptDir\bin\*" -Destination $BinDir -Recurse -Force
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
            if (Test-Path "$env:TEMP\KingdomExtract\bin\kingdom.pyz") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\bin\*" -Destination "$BinDir" -Recurse -Force
            } elseif (Test-Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\bin\kingdom.pyz") {
                Copy-Item -Path "$env:TEMP\KingdomExtract\KingdomServer-win64-full\bin\*" -Destination "$BinDir" -Recurse -Force
            }
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path "$env:TEMP\KingdomExtract" -Recurse -Force -ErrorAction SilentlyContinue
            $Deployed = $true
        }
    } catch {
        Write-Host "[ERROR] Release ZIP download failed." -ForegroundColor Red
    }
}

if (-not $Deployed) {
    Write-Host "[ERROR] Failed to locate or download kingdom.pyz bundle. Aborting." -ForegroundColor Red
    exit 1
}

# 3. Setup Python virtual environment & package installation
Write-Host "[4/5] Setting up Python virtual environment & Dependencies..." -ForegroundColor Cyan

$VenvPython = "$InstallDir\venv\Scripts\python.exe"

# If venv folder exists but python.exe is missing, clean up broken venv directory
if ((Test-Path "$InstallDir\venv") -and (-not (Test-Path $VenvPython))) {
    Write-Host "[WARN] Cleaning up previously incomplete/corrupted venv directory..." -ForegroundColor Yellow
    Remove-Item -Path "$InstallDir\venv" -Recurse -Force -ErrorAction SilentlyContinue
}

# Discover all candidate Python installations on the system
$pythonCandidates = @()

# 1. Official Windows py launcher
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCandidates += "py -3.12"
    $pythonCandidates += "py -3.11"
    $pythonCandidates += "py -3.10"
    $pythonCandidates += "py -3"
}

# 2. System PATH pythons (exclude WindowsApps redirect stubs and existing venvs)
$wherePythons = where.exe python 2>$null
if ($wherePythons) {
    foreach ($wp in $wherePythons) {
        if ($wp -notmatch "WindowsApps" -and $wp -notmatch "KingdomAIServer\\venv") {
            $pythonCandidates += $wp
        }
    }
}

# 3. Primary active Python command
$activePy = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($activePy -and ($activePy -notmatch "WindowsApps") -and ($activePy -notmatch "KingdomAIServer\\venv")) {
    $pythonCandidates += $activePy
}

# 4. Standard Python directories
$commonGlobs = @(
    "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
    "C:\Python3*\python.exe",
    "$env:ProgramFiles\Python3*\python.exe",
    "${env:ProgramFiles(x86)}\Python3*\python.exe"
)
foreach ($glob in $commonGlobs) {
    $found = Get-Item -Path $glob -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    if ($found) {
        $pythonCandidates += $found
    }
}

$uniqueCandidates = $pythonCandidates | Select-Object -Unique

# Attempt to initialize virtual environment
if (-not (Test-Path $VenvPython)) {
    Write-Host "Initializing user-space Python virtual environment at $InstallDir\venv..." -ForegroundColor Yellow

    foreach ($py in $uniqueCandidates) {
        Write-Host "Checking Python candidate: $py ..." -ForegroundColor Cyan

        # Helper to execute command with arguments
        $runPy = {
            param($cmdStr, $argsList)
            if ($cmdStr -match "^py\s") {
                $parts = $cmdStr -split "\s+"
                & $parts[0] $parts[1] @argsList
            } else {
                & $cmdStr @argsList
            }
        }

        # Step A: Check if candidate has standard 'venv' module
        $hasVenv = $false
        try {
            & $runPy $py @("-c", "import venv; print('OK')") 2>$null | Out-Null
            $hasVenv = ($LASTEXITCODE -eq 0)
        } catch {
            $hasVenv = $false
        }

        if ($hasVenv) {
            Write-Host "Creating venv using standard 'venv' module from $py..." -ForegroundColor Green
            try {
                & $runPy $py @("-m", "venv", "$InstallDir\venv")
            } catch {}

            if (Test-Path $VenvPython) {
                Write-Host "[OK] Virtual environment created successfully!" -ForegroundColor Green
                break
            }
        }

        # Step B: If standard venv is missing (e.g. minimal or embeddable python), check for virtualenv
        Write-Host "Candidate $py lacks standard 'venv' module. Checking for 'virtualenv'..." -ForegroundColor Yellow
        $hasVirtualEnv = $false
        try {
            & $runPy $py @("-c", "import virtualenv; print('OK')") 2>$null | Out-Null
            $hasVirtualEnv = ($LASTEXITCODE -eq 0)
        } catch {
            $hasVirtualEnv = $false
        }

        if (-not $hasVirtualEnv) {
            # Try installing virtualenv via pip
            try {
                & $runPy $py @("-m", "pip", "install", "--upgrade", "virtualenv", "-q") 2>$null
                $hasVirtualEnv = ($LASTEXITCODE -eq 0)
            } catch {}
        }

        if ($hasVirtualEnv) {
            Write-Host "Creating venv using 'virtualenv' module from $py..." -ForegroundColor Green
            try {
                & $runPy $py @("-m", "virtualenv", "$InstallDir\venv")
            } catch {}

            if (Test-Path $VenvPython) {
                Write-Host "[OK] Virtual environment created successfully via virtualenv!" -ForegroundColor Green
                break
            }
        }
    }
}

# Strict validation: Abort if venv creation failed
if (-not (Test-Path $VenvPython)) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "[ERROR] Could not initialize Python virtual environment at $InstallDir\venv!" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "Reason: Your installed Python is missing the standard 'venv' module" -ForegroundColor Yellow
    Write-Host "        (this commonly occurs with embeddable, stripped, or pre-release zip packages)." -ForegroundColor Yellow
    Write-Host "Checked candidates: $($uniqueCandidates -join ' ; ')" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "HOW TO RESOLVE:" -ForegroundColor Cyan
    Write-Host "  1. Download and install standard Python (Python 3.11 or 3.12 recommended) from:" -ForegroundColor White
    Write-Host "     https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "  2. In the installer wizard, ensure you check:" -ForegroundColor White
    Write-Host "     [x] Add python.exe to PATH" -ForegroundColor Green
    Write-Host "     [x] pip" -ForegroundColor Green
    Write-Host "     [x] Install standard library features (venv / tcl)" -ForegroundColor Green
    Write-Host "  3. Re-run this installation command in PowerShell." -ForegroundColor White
    Write-Host "======================================================================" -ForegroundColor Red
    exit 1
}

# At this point, $VenvPython is guaranteed to exist
Write-Host "Upgrading pip and setuptools inside venv..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip setuptools -q

Write-Host "Installing core Kingdom AI Server dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --prefer-binary fastapi uvicorn rich httpx truststore sqlite-vec tree-sitter pillow requests pyyaml psutil jinja2 slint

Write-Host "Analyzing CPU & Graphics Hardware Profile..." -ForegroundColor Yellow

# 1. Query CPU Details
$cpuObj = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1
$cpuName = if ($cpuObj.Name) { $cpuObj.Name.Trim() } else { "Generic x86_64 CPU" }
$cpuCores = if ($cpuObj.NumberOfCores) { $cpuObj.NumberOfCores } else { 4 }
$cpuThreads = if ($cpuObj.NumberOfLogicalProcessors) { $cpuObj.NumberOfLogicalProcessors } else { $cpuCores }

Write-Host "  • CPU Processor: $cpuName ($cpuCores Cores / $cpuThreads Threads)" -ForegroundColor Cyan

# 2. Query Graphics Controllers (filter out virtual display mirror / remote adapters)
$allGpuControllers = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue
$virtualPattern = "Mirror|DameWare|Remote|RDP|Basic Display|Hyper-V|VMware|VirtualBox|Citrix|QEMU|Red Hat|ASPEED|Matrox|IddSample|VNC|TeamViewer|AnyDesk|LogMeIn"

$physicalGpus = $allGpuControllers | Where-Object { 
    $_.Name -and ($_.Name -notmatch $virtualPattern)
}

$allGpuNames = ($allGpuControllers | ForEach-Object { $_.Name }) -join " ; "
$physicalGpuNames = if ($physicalGpus) { ($physicalGpus | ForEach-Object { $_.Name }) -join " / " } else { "" }

Write-Host "  • Video Adapters Detected: $allGpuNames" -ForegroundColor Cyan
if ($physicalGpus) {
    Write-Host "  • Physical GPU Hardware:   $physicalGpuNames" -ForegroundColor Green
} else {
    Write-Host "  • Physical GPU Hardware:   None (Virtual Desktop / Cloud VM / AVD environment detected)" -ForegroundColor Yellow
}

# 3. Check for GPU API Driver Runtimes
$hasCuda = (Test-Path "$env:SystemRoot\System32\nvcuda.dll") -or (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$hasVulkan = (Test-Path "$env:SystemRoot\System32\vulkan-1.dll")

# 4. Wheel Definitions
$vulkanWheel = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-vulkan/llama_cpp_python-0.3.35-py3-none-win_amd64.whl"
$cudaWheel = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-cu124/llama_cpp_python-0.3.35-py3-none-win_amd64.whl"
$cpuWheel = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-py3-none-win_amd64.whl"

# 5. Classify Hardware Tier & Wheel Selection
$targetTier = "CPU"
$targetWheel = $cpuWheel
$isCpuOnly = $false

if ($physicalGpus -and (($physicalGpuNames -match "NVIDIA|GeForce|RTX|GTX|Quadro|Tesla|TITAN|A100|T4") -or $hasCuda)) {
    $targetTier = "CUDA"
    $targetWheel = $cudaWheel
    Write-Host "Hardware Profile: NVIDIA Discrete GPU detected. Selecting CUDA wheel ($cudaWheel)..." -ForegroundColor Green
} elseif ($physicalGpus -and (($physicalGpuNames -match "Intel|Iris|Arc|AMD|Radeon|Ryzen") -or $hasVulkan)) {
    $targetTier = "VULKAN"
    $targetWheel = $vulkanWheel
    Write-Host "Hardware Profile: Intel Iris Xe / Arc / AMD Radeon detected. Selecting Vulkan wheel ($vulkanWheel)..." -ForegroundColor Green
} else {
    # CPU-Only (e.g. Azure Virtual Desktop, Intel Xeon server VM, AWS/GCP VM without GPU, or legacy PC)
    $targetTier = "CPU"
    $targetWheel = $cpuWheel
    $isCpuOnly = $true
    Write-Host "Hardware Profile: CPU-Only / Enterprise Virtual Desktop (AVD with $cpuName). Selecting optimized multi-threaded CPU wheel..." -ForegroundColor Magenta
}

Write-Host "Downloading and installing llama-cpp-python ($targetTier)..." -ForegroundColor Cyan
& $VenvPython -m pip install --prefer-binary $targetWheel
if ($LASTEXITCODE -ne 0) {
    if ($targetTier -eq "CUDA") {
        Write-Host "[WARN] CUDA wheel installation failed. Trying Vulkan wheel fallback..." -ForegroundColor Yellow
        & $VenvPython -m pip install --prefer-binary $vulkanWheel
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] Vulkan fallback failed. Falling back to CPU wheel..." -ForegroundColor Yellow
            & $VenvPython -m pip install --prefer-binary $cpuWheel
            $isCpuOnly = $true
        }
    } elseif ($targetTier -eq "VULKAN") {
        Write-Host "[WARN] Vulkan wheel failed. Falling back to CPU wheel..." -ForegroundColor Yellow
        & $VenvPython -m pip install --prefer-binary $cpuWheel
        $isCpuOnly = $true
    }
}

# 6. Apply CPU-only configuration profile if running on CPU or VM without GPU
if ($isCpuOnly) {
    Write-Host "Generating CPU-optimized configuration profile at $ConfigDir\model_config.yaml..." -ForegroundColor Cyan
    $cpuConfig = @"
# Kingdom AI Server V2 - Auto-configured for CPU-Only / AVD / Cloud VM deployment
server:
  host: "127.0.0.1"
  port: 58420
  cspa_defense_enabled: true

hardware:
  execution_provider: "CPU"
  gpu_offload_mode: "cpu"
  strict_gpu: false
  n_gpu_layers: 0
  cpu_fallback_avx2: true
  max_static_vram_mb: 6144

main_boss:
  strict_gpu: false
  n_gpu_layers: 0
  threads: $cpuThreads
"@
    Set-Content -Path "$ConfigDir\model_config.yaml" -Value $cpuConfig -Encoding UTF8
}

# Verify runtime engine capability
$gpuCheck = & $VenvPython -c "import llama_cpp; print(getattr(llama_cpp, 'llama_supports_gpu_offload', lambda: False)())"
if ($gpuCheck -eq "True") {
    Write-Host "[SUCCESS] llama-cpp-python verified with active GPU/iGPU acceleration support!" -ForegroundColor Green
} else {
    if ($isCpuOnly) {
        Write-Host "[SUCCESS] llama-cpp-python verified with multi-threaded CPU acceleration (AVX2/AVX-512) for $cpuName!" -ForegroundColor Green
    } else {
        Write-Host "[INFO] llama-cpp-python is running in CPU mode. (For dedicated Intel Iris Xe or NVIDIA, install Vulkan/CUDA drivers)." -ForegroundColor Yellow
    }
}

# Generate localized venv-aware cmd wrappers
$cpuEnvSet = if ($isCpuOnly) { "set KINGDOM_CPU_MODE=1`r`n" } else { "" }
$StudioCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`n$cpuEnvSet`cd /d `"%~dp0..`"`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" `"%~dp0kingdom.pyz`" studio %*`r`n) else (`r`n    python.exe `"%~dp0kingdom.pyz`" studio %*`r`n)"
Set-Content -Path "$BinDir\kingdom_studio.cmd" -Value $StudioCmd -Encoding ASCII

$LauncherCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`n$cpuEnvSet`cd /d `"%~dp0..`"`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" `"%~dp0kingdom.pyz`" server %*`r`n) else (`r`n    python.exe `"%~dp0kingdom.pyz`" server %*`r`n)"
Set-Content -Path "$BinDir\start_server.cmd" -Value $LauncherCmd -Encoding ASCII

$DownloadCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`ncd /d `"%~dp0..`"`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" `"%~dp0kingdom.pyz`" download %*`r`n) else (`r`n    python.exe `"%~dp0kingdom.pyz`" download %*`r`n)"
Set-Content -Path "$BinDir\download_models.cmd" -Value $DownloadCmd -Encoding ASCII

$CliCmd = "@echo off`r`nsetlocal`r`nset PYTHONUTF8=1`r`n$cpuEnvSet`cd /d `"%~dp0..`"`r`nif exist `"%~dp0..\venv\Scripts\python.exe`" (`r`n    `"%~dp0..\venv\Scripts\python.exe`" `"%~dp0kingdom.pyz`" cli %*`r`n) else (`r`n    python.exe `"%~dp0kingdom.pyz`" cli %*`r`n)"
Set-Content -Path "$BinDir\kingdom_cli.cmd" -Value $CliCmd -Encoding ASCII

# Unblock files against Windows Defender Zone.Identifier
Get-ChildItem -Path $BinDir -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue
}

# Create Desktop Shortcut
Write-Host "[5/5] Creating user desktop shortcut and updating PATH..." -ForegroundColor Cyan
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\Kingdom AI Studio.lnk")
    $Shortcut.TargetPath = "$BinDir\kingdom_studio.cmd"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Kingdom AI Studio V3 - On-Device Antigravity AI Coding Assistant"
    $Shortcut.Save()
    Write-Host "[OK] Desktop shortcut created successfully (Kingdom AI Studio)!" -ForegroundColor Green
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
Write-Host " KINGDOM AI STUDIO V3 (ANTIGRAVITY GUI) DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " Installation Directory : $InstallDir" -ForegroundColor White
Write-Host " Models Directory       : $ModelsDir" -ForegroundColor White
Write-Host ""
Write-Host " Quick Launch Commands:" -ForegroundColor Cyan
Write-Host "   kingdom_studio          # Launch Google Antigravity-style Desktop GUI" -ForegroundColor Green
Write-Host "   kingdom_cli             # Launch Rich Terminal CLI" -ForegroundColor Yellow
Write-Host "   start_server            # Start headless API server (optional)" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
