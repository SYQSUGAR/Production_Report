@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Production Report - Stop Reference Database

set "MYSQL_HOME=D:\3SoftWare\mysql"
set "DB_PORT=3307"
set "INSTANCE_ROOT=%MYSQL_HOME%\production_report_demo"
set "RUN_DIR=%INSTANCE_ROOT%\run"
set "PID_FILE=%RUN_DIR%\mysqld.pid"

echo Stopping Production Report reference MySQL database...
echo.

set "MYSQLADMIN="
if exist "%MYSQL_HOME%\bin\mysqladmin.exe" set "MYSQLADMIN=%MYSQL_HOME%\bin\mysqladmin.exe"
if not defined MYSQLADMIN if exist "%MYSQL_HOME%" for /r "%MYSQL_HOME%" %%F in (mysqladmin.exe) do if not defined MYSQLADMIN set "MYSQLADMIN=%%~fF"

rem Try a clean shutdown first.
if defined MYSQLADMIN (
    "%MYSQLADMIN%" --no-defaults --protocol=tcp --host=127.0.0.1 --port=%DB_PORT% --user=root shutdown >nul 2>&1
)

timeout /t 1 /nobreak >nul

rem If clean shutdown did not finish, force-stop ONLY the PID recorded
rem for this dedicated test instance. Never kill all mysqld.exe processes.
if exist "%PID_FILE%" (
    set "DB_PID="
    set /p DB_PID=<"%PID_FILE%"
    if defined DB_PID (
        tasklist /FI "PID eq !DB_PID!" /FO CSV /NH 2>nul | findstr /I "mysqld.exe" >nul
        if not errorlevel 1 (
            echo Clean shutdown did not finish. Force-stopping dedicated PID !DB_PID!...
            taskkill /PID !DB_PID! /T /F >nul 2>&1
            timeout /t 1 /nobreak >nul
        )
    )
)

if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1

echo.
echo Database stopped.
echo Saved data remains in:
echo   %INSTANCE_ROOT%\data
echo.
echo No Python, Anaconda, PyQt, or other MySQL process was stopped.
timeout /t 3 /nobreak >nul
endlocal & exit /b 0
