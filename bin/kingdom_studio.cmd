@echo off
REM Kingdom AI Studio V3 - Google Antigravity Desktop GUI Launcher
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
"%PYTHON_EXE%" main.py %*
