@echo off
cd /d "%~dp0"
title Production Report - Local MySQL Launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\local_launcher.ps1"
exit /b %ERRORLEVEL%
