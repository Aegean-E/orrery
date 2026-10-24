@echo off
setlocal
cd /d "%~dp0"
title Orrery - N-body sandbox

set "PY="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python 3.10 or newer was not found.
    echo Install Python, enable "Add python.exe to PATH", and run this file again.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    %PY% -m orrery run solar
) else (
    %PY% -m orrery run %*
)
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" echo Orrery exited with code %CODE%.
pause
exit /b %CODE%
