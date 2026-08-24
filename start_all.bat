@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Production Report - Local MySQL Launcher

rem ============================================================
rem Production Report one-click launcher
rem Uses the existing MySQL installation under D:\3SoftWare\mysql.
rem It starts a DEDICATED test instance on 127.0.0.1:3307 with its
rem own data directory, so it will not touch a normal MySQL service
rem that may already be using port 3306.
rem ============================================================

set "MYSQL_HOME=D:\3SoftWare\mysql"
set "DB_PORT=3307"
set "INSTANCE_ROOT=%MYSQL_HOME%\production_report_demo"
set "DB_DATA=%INSTANCE_ROOT%\data"
set "RUN_DIR=%INSTANCE_ROOT%\run"
set "LOG_DIR=%INSTANCE_ROOT%\logs"
set "PID_FILE=%RUN_DIR%\mysqld.pid"
set "APP_PID_FILE=%RUN_DIR%\app.pid"
set "LOG_FILE=%LOG_DIR%\mysql-error.log"
set "SCHEMA_CHECK=%RUN_DIR%\schema-check.txt"
set "PROJECT_DIR=%~dp0"

call :find_python
if errorlevel 1 goto :fatal

call :find_mysql_tools
if errorlevel 1 goto :fatal

if not exist "%INSTANCE_ROOT%" mkdir "%INSTANCE_ROOT%"
if not exist "%DB_DATA%" mkdir "%DB_DATA%"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call :check_existing_app
if errorlevel 2 goto :already_running

call :prepare_database
if errorlevel 1 goto :fatal

call :start_or_reuse_database
if errorlevel 1 goto :fatal

call :ensure_reference_databases
if errorlevel 1 goto :cleanup_error

echo.
echo ============================================================
echo Reference database is ready.
echo Host     : 127.0.0.1
echo Port     : %DB_PORT%
echo User     : report_user
echo Password : report123
echo Databases:
echo   production_basic_demo
echo   production_energy_demo
echo   production_operation_demo
echo   production_maintenance_demo
echo ============================================================
echo.
echo Starting Production Report application...
echo Close the PyQt window normally and this launcher will stop
 echo the dedicated MySQL instance automatically.
echo.

call :run_application
set "APP_EXIT=%ERRORLEVEL%"

if exist "%APP_PID_FILE%" del /q "%APP_PID_FILE%" >nul 2>&1

echo.
echo Application closed. Stopping dedicated MySQL instance...
call :stop_database
if errorlevel 1 (
    echo [WARN] Normal shutdown failed. Run stop_all.bat to force-stop it.
) else (
    echo Database stopped. Saved data is preserved in:
    echo   %DB_DATA%
)

endlocal & exit /b %APP_EXIT%

:find_python
set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE if exist "%PYTHON_EXE%" exit /b 0
set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE if exist "%PYTHON_EXE%" exit /b 0
echo [ERROR] Python was not found.
echo Please make sure Python is installed and can run from CMD.
exit /b 1

:find_mysql_tools
if not exist "%MYSQL_HOME%" (
    echo [ERROR] MySQL directory does not exist:
    echo   %MYSQL_HOME%
    exit /b 1
)

set "MYSQLD="
set "MYSQL="
set "MYSQLADMIN="

if exist "%MYSQL_HOME%\bin\mysqld.exe" set "MYSQLD=%MYSQL_HOME%\bin\mysqld.exe"
if exist "%MYSQL_HOME%\bin\mysql.exe" set "MYSQL=%MYSQL_HOME%\bin\mysql.exe"
if exist "%MYSQL_HOME%\bin\mysqladmin.exe" set "MYSQLADMIN=%MYSQL_HOME%\bin\mysqladmin.exe"

if not defined MYSQLD for /r "%MYSQL_HOME%" %%F in (mysqld.exe) do if not defined MYSQLD set "MYSQLD=%%~fF"
if not defined MYSQL for /r "%MYSQL_HOME%" %%F in (mysql.exe) do if not defined MYSQL set "MYSQL=%%~fF"
if not defined MYSQLADMIN for /r "%MYSQL_HOME%" %%F in (mysqladmin.exe) do if not defined MYSQLADMIN set "MYSQLADMIN=%%~fF"

if not defined MYSQLD (
    echo [ERROR] mysqld.exe was not found under %MYSQL_HOME%
    exit /b 1
)
if not defined MYSQL (
    echo [ERROR] mysql.exe was not found under %MYSQL_HOME%
    exit /b 1
)
if not defined MYSQLADMIN (
    echo [ERROR] mysqladmin.exe was not found under %MYSQL_HOME%
    exit /b 1
)

for %%I in ("%MYSQLD%") do set "MYSQL_BIN_DIR=%%~dpI"
for %%I in ("!MYSQL_BIN_DIR!..") do set "MYSQL_BASE=%%~fI"
exit /b 0

:check_existing_app
if not exist "%APP_PID_FILE%" exit /b 0
set "OLD_APP_PID="
set /p OLD_APP_PID=<"%APP_PID_FILE%"
if not defined OLD_APP_PID (
    del /q "%APP_PID_FILE%" >nul 2>&1
    exit /b 0
)
tasklist /FI "PID eq !OLD_APP_PID!" /FO CSV /NH 2>nul | findstr /C:"!OLD_APP_PID!" >nul
if errorlevel 1 (
    del /q "%APP_PID_FILE%" >nul 2>&1
    exit /b 0
)
echo [INFO] Production Report is already running. PID=!OLD_APP_PID!
exit /b 2

:prepare_database
if exist "%DB_DATA%\mysql" exit /b 0

echo.
echo [1/4] First run: initializing dedicated MySQL data directory...
echo       %DB_DATA%
"%MYSQLD%" --no-defaults --initialize-insecure --basedir="%MYSQL_BASE%" --datadir="%DB_DATA%"
if errorlevel 1 (
    echo [ERROR] MySQL data directory initialization failed.
    echo Check whether this MySQL installation is complete.
    exit /b 1
)
exit /b 0

:start_or_reuse_database
set "OWN_DB_RUNNING=0"
set "DB_PID="

if exist "%PID_FILE%" (
    set /p DB_PID=<"%PID_FILE%"
    if defined DB_PID (
        tasklist /FI "PID eq !DB_PID!" /FO CSV /NH 2>nul | findstr /I "mysqld.exe" >nul
        if not errorlevel 1 set "OWN_DB_RUNNING=1"
    )
)

if "!OWN_DB_RUNNING!"=="1" (
    echo.
    echo [2/4] Dedicated MySQL is already running. Reusing PID !DB_PID!.
    call :wait_for_mysql
    exit /b !ERRORLEVEL!
)

if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1

netstat -ano -p tcp | findstr /R /C:":%DB_PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port %DB_PORT% is already occupied by another process.
    echo For safety this launcher will NOT stop or reuse an unknown server.
    exit /b 1
)

echo.
echo [2/4] Starting dedicated MySQL on 127.0.0.1:%DB_PORT%...
start "" /B "%MYSQLD%" --no-defaults --basedir="%MYSQL_BASE%" --datadir="%DB_DATA%" --port=%DB_PORT% --bind-address=127.0.0.1 --pid-file="%PID_FILE%" --log-error="%LOG_FILE%" --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci

call :wait_for_mysql
if errorlevel 1 (
    echo [ERROR] MySQL did not become ready in time.
    echo Error log:
    echo   %LOG_FILE%
    exit /b 1
)
exit /b 0

:wait_for_mysql
for /L %%I in (1,1,60) do (
    "%MYSQLADMIN%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot ping --silent >nul 2>&1
    if not errorlevel 1 exit /b 0
    timeout /t 1 /nobreak >nul
)
exit /b 1

:ensure_reference_databases
echo.
echo [3/4] Checking reference databases...
"%MYSQL%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot -N -B -e "SHOW DATABASES LIKE 'production_basic_demo';" >"%SCHEMA_CHECK%" 2>nul
findstr /X /C:"production_basic_demo" "%SCHEMA_CHECK%" >nul 2>&1
if not errorlevel 1 (
    del /q "%SCHEMA_CHECK%" >nul 2>&1
    echo       Existing reference databases found. No re-import needed.
    exit /b 0
)
if exist "%SCHEMA_CHECK%" del /q "%SCHEMA_CHECK%" >nul 2>&1

echo       First database start: importing SQL reference data...
call :import_sql "reference_database\01_basic_data.sql"
if errorlevel 1 exit /b 1
call :import_sql "reference_database\02_energy_data.sql"
if errorlevel 1 exit /b 1
call :import_sql "reference_database\03_operation_data.sql"
if errorlevel 1 exit /b 1
call :import_sql "reference_database\04_maintenance_data.sql"
if errorlevel 1 exit /b 1
call :import_sql "reference_database\06_grant_reference_user.sql"
if errorlevel 1 exit /b 1

echo       Reference databases imported successfully.
exit /b 0

:import_sql
if not exist "%~dp0%~1" (
    echo [ERROR] Missing SQL file: %~1
    exit /b 1
)
"%MYSQL%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot < "%~dp0%~1"
if errorlevel 1 (
    echo [ERROR] Failed to import: %~1
    exit /b 1
)
exit /b 0

:run_application
echo.
echo [4/4] Starting PyQt application...
set "PYTHON_EXE_ENV=%PYTHON_EXE%"
set "APP_PID_FILE_ENV=%APP_PID_FILE%"
set "PROJECT_DIR_ENV=%PROJECT_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath $env:PYTHON_EXE_ENV -ArgumentList 'main.py' -WorkingDirectory $env:PROJECT_DIR_ENV -PassThru; [System.IO.File]::WriteAllText($env:APP_PID_FILE_ENV,[string]$p.Id); $p.WaitForExit(); exit $p.ExitCode"
exit /b %ERRORLEVEL%

:stop_database
"%MYSQLADMIN%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot shutdown >nul 2>&1
for /L %%I in (1,1,15) do (
    if not exist "%PID_FILE%" exit /b 0
    set "STOP_PID="
    set /p STOP_PID=<"%PID_FILE%"
    if not defined STOP_PID exit /b 0
    tasklist /FI "PID eq !STOP_PID!" /FO CSV /NH 2>nul | findstr /I "mysqld.exe" >nul
    if errorlevel 1 (
        del /q "%PID_FILE%" >nul 2>&1
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
exit /b 1

:cleanup_error
call :stop_database >nul 2>&1
goto :fatal

:already_running
echo.
echo Another Production Report window is already running.
echo This launcher will not open a second application or database instance.
timeout /t 3 /nobreak >nul
endlocal & exit /b 0

:fatal
echo.
echo Startup failed.
echo No unknown MySQL service will be killed by this launcher.
echo If the dedicated test instance remains running, use stop_all.bat.
pause
endlocal & exit /b 1
