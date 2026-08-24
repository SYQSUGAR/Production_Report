@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Production Report - Start Database

rem ============================================================
rem Start ONLY the dedicated reference MySQL instance.
rem PyQt is intentionally independent and is NOT started here.
rem Existing MySQL installation: D:\3SoftWare\mysql
rem Dedicated test instance: 127.0.0.1:3307
rem ============================================================

set "MYSQL_HOME=D:\3SoftWare\mysql"
set "DB_PORT=3307"
set "INSTANCE_ROOT=%MYSQL_HOME%\production_report_demo"
set "DB_DATA=%INSTANCE_ROOT%\data"
set "RUN_DIR=%INSTANCE_ROOT%\run"
set "LOG_DIR=%INSTANCE_ROOT%\logs"
set "PID_FILE=%RUN_DIR%\mysqld.pid"
set "LOG_FILE=%LOG_DIR%\mysql-error.log"
set "SCHEMA_CHECK=%RUN_DIR%\schema-check.txt"

call :find_mysql_tools
if errorlevel 1 goto :fatal

if not exist "%INSTANCE_ROOT%" mkdir "%INSTANCE_ROOT%"
if not exist "%DB_DATA%" mkdir "%DB_DATA%"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call :prepare_database
if errorlevel 1 goto :fatal

call :start_or_reuse_database
if errorlevel 1 goto :fatal

call :ensure_reference_databases
if errorlevel 1 goto :cleanup_error

echo.
echo ============================================================
echo Reference MySQL is running in background.
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
echo This BAT can now close. The database will keep running.
echo To stop ONLY this test database, run stop_database.bat.
timeout /t 4 /nobreak >nul
endlocal & exit /b 0

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

:prepare_database
if exist "%DB_DATA%\mysql" exit /b 0

echo.
echo [1/3] First run: initializing dedicated MySQL data directory...
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
    echo [2/3] Dedicated MySQL is already running. Reusing PID !DB_PID!.
    call :wait_for_mysql
    exit /b !ERRORLEVEL!
)

if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1

netstat -ano -p tcp | findstr /R /C:":%DB_PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port %DB_PORT% is already occupied by another process.
    echo For safety, this launcher will NOT stop or reuse an unknown server.
    exit /b 1
)

echo.
echo [2/3] Starting dedicated MySQL on 127.0.0.1:%DB_PORT%...
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
echo [3/3] Checking reference databases...
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

:stop_database
"%MYSQLADMIN%" --no-defaults --protocol=tcp -h127.0.0.1 -P%DB_PORT% -uroot shutdown >nul 2>&1
exit /b 0

:cleanup_error
call :stop_database >nul 2>&1
goto :fatal

:fatal
echo.
echo Startup failed.
echo No PyQt process and no unrelated MySQL service was touched.
echo If this dedicated instance remains running, use stop_database.bat.
pause
endlocal & exit /b 1
