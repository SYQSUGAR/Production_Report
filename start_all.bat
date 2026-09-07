@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Production Report - Start Reference Database

echo Starting the Production Report reference MySQL server...
echo This script starts the database only; it does not start Python or PyQt.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\local_launcher.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Database launcher returned error code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
