@echo off
REM [DEPRECATED in V3] Kingdom AI Server - Legacy Terminal CLI Launcher
REM Redirects to Kingdom AI Studio V3 Slint Native Desktop GUI
REM Runs via corporate-approved python.exe (no .exe binaries)
setlocal
set PYTHONUTF8=1

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

REM Prefer venv python, fall back to system python
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set PYTHON_EXE=%PROJECT_ROOT%\venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m src.cli.terminal_ui %*
