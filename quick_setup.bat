@echo off
rem quick_setup.bat — Windows portable venv-first setup bootstrapper.
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ==========================================
echo 🚀 Bootstrapping Instagram MCP Setup on Windows...
echo ==========================================

set "FOUND_PY="

rem Check py candidate
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -c "import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if !errorlevel! equ 0 (
        set "FOUND_PY=py"
        goto RUN
    )
)

rem Check python candidate
where python >nul 2>nul
if %errorlevel% equ 0 (
    python -c "import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if !errorlevel! equ 0 (
        set "FOUND_PY=python"
        goto RUN
    )
)

rem Check python3 candidate
where python3 >nul 2>nul
if %errorlevel% equ 0 (
    python3 -c "import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if !errorlevel! equ 0 (
        set "FOUND_PY=python3"
        goto RUN
    )
)

echo ❌ Suitable Python interpreter not found.
echo Requirements:
echo   - Python version ^>= 3.11
echo   - Standard library 'venv' module installed
echo.
echo Please install Python 3.11+ (make sure to select "Add Python to PATH" during installation)
echo.
pause
exit /b 1

:RUN
echo ✓ Detected Python interpreter: !FOUND_PY!
echo ✓ Python version validation passed.
echo ==========================================

!FOUND_PY! setup.py --interpreter !FOUND_PY!
if %errorlevel% neq 0 (
    echo ❌ Setup execution failed.
    pause
    exit /b %errorlevel%
)
