@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Production Report - Stop All

set "MYSQL_HOME=D:\3SoftWare\mysql"
set "DB_PORT=3307"
set "INSTANCE_ROOT=%MYSQL_HOME%\production_report_demo"
set "RUN_DIR=%INSTANCE_ROOT%\run"
set "PID_FILE=%RUN_DIR%\mysqld.pid"
set "APP_PID_FILE=%RUN_DIR%\app.pid"

echo Stopping Production Report application and dedicated MySQL...
echo.

rem Stop only the PyQt process whose PID was written by start_all.bat.
if exist "%APP_PID_FILE%" (
    set "APP_PID="
    set /p APP_PID=<"%APP_PID_FILE%"
    if defined APP_PID (
        tasklist /FI "PID eq !APP_PID!" /FO CSV /NH 2>nul | findstr /C:"!APP_PID!" >nul
        if not errorlevel 1 (
            echo Stopping PyQt application. PID=!APP_PID!
            taskkill /PID !APP_PID! /T >nul 2>&1
            timeout /t 1 /nobreak >nul
        )
    )
    del /q "%APP_PID_FILE%" >nul 2>&1
)

set "MYSQLADMIN="
if exist "%MYSQL_HOME%\bin\mysqladmin.exe" set "MYSQLADMIN=%MYSQL_HOME%\bin\mysqladmin.exe"
if not defined MYSQLADMIN if exist "%MYSQL_HOME%" for /r "%MYSQL_HOME%" %%F in (mysqladmin.exe) do if not defined MYSQLADMIN set "MYSQLADMIN=%%~fF"

rem Try a clean shutdown first. This dedicated instance has an empty root
rem password and is bound only to 127.0.0.1:3307.
if defined MYSQLADMIN (
    "%MYSQLADMIN%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot shutdown >nul 2>&1
)

timeout /t 1 /nobreak >nul

rem If clean shutdown failed, use ONLY the PID file of our dedicated instance.
rem Never use taskkill /IM mysqld.exe, because that could kill another MySQL.
if exist "%PID_FILE%" (
    set "DB_PID="
    set /p DB_PID=<"%PID_FILE%"
    if defined DB_PID (
        tasklist /FI "PID eq !DB_PID!" /FO CSV /NH 2>nul | findstr /I "mysqld.exe" >nul
        if not errorlevel 1 (
            echo Clean database shutdown did not finish. Force-stopping dedicated PID !DB_PID!...
            taskkill /PID !DB_PID! /T /F >nul 2>&1
            timeout /t 1 /nobreak >nul
        )
    )
)

if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1

echo.
echo Done.
echo The dedicated test database is stopped.
echo Saved data remains in:
echo   %INSTANCE_ROOT%\data
echo.
echo This script does NOT stop any other MySQL service on your computer.
timeout /t 3 /nobreak >nul
endlocal & exit /b 0
