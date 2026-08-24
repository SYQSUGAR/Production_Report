@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Production Report - Launcher

set "COMPOSE_FILE=%~dp0docker-compose.yml"
set "CONTAINER_NAME=production-report-mysql"
set "DB_PORT=3307"
set "DB_STARTED=0"

call :check_python
if errorlevel 1 goto :fatal

call :check_docker
if errorlevel 1 goto :fatal

call :ensure_docker_engine
if errorlevel 1 goto :fatal

echo.
echo [1/3] Starting reference MySQL database...
docker compose -f "%COMPOSE_FILE%" up -d mysql
if errorlevel 1 (
    echo [ERROR] Failed to start MySQL container.
    goto :fatal
)
set "DB_STARTED=1"

call :wait_for_mysql
if errorlevel 1 (
    echo [ERROR] MySQL did not become healthy in time.
    docker logs --tail 80 "%CONTAINER_NAME%"
    goto :cleanup_error
)

echo.
echo [2/3] Database is ready.
echo       Host: 127.0.0.1
    echo       Port: %DB_PORT%
echo       User: report_user
echo       Password: report123
echo       Databases: production_basic_demo / production_energy_demo /
echo                  production_operation_demo / production_maintenance_demo

echo.
echo [3/3] Starting Production Report application...
echo       Close the PyQt window normally to stop the database automatically.
echo.

%PYTHON_CMD% main.py
set "APP_EXIT=%ERRORLEVEL%"

echo.
echo Application closed. Stopping reference database...
docker compose -f "%COMPOSE_FILE%" stop mysql >nul 2>&1
if errorlevel 1 docker stop "%CONTAINER_NAME%" >nul 2>&1

echo Database stopped. Data volume has been preserved.
endlocal & exit /b %APP_EXIT%

:check_python
set "PYTHON_CMD="
where python >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if defined PYTHON_CMD exit /b 0
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py"
if defined PYTHON_CMD exit /b 0
echo [ERROR] Python was not found in PATH.
echo Install Python or add it to PATH before using this launcher.
exit /b 1

:check_docker
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker command was not found.
    echo Please install Docker Desktop first.
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is unavailable.
    echo Please update Docker Desktop to a version with "docker compose".
    exit /b 1
)
exit /b 0

:ensure_docker_engine
docker info >nul 2>&1
if not errorlevel 1 exit /b 0

echo Docker Desktop is installed but its engine is not running.
set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not exist "%DOCKER_DESKTOP%" (
    echo [ERROR] Docker Desktop executable was not found at:
    echo         %DOCKER_DESKTOP%
    echo Start Docker Desktop manually, then run this BAT again.
    exit /b 1
)

echo Starting Docker Desktop...
start "" "%DOCKER_DESKTOP%"
for /L %%I in (1,1,90) do (
    docker info >nul 2>&1
    if not errorlevel 1 exit /b 0
    timeout /t 2 /nobreak >nul
)

echo [ERROR] Docker engine did not become ready within 180 seconds.
exit /b 1

:wait_for_mysql
for /L %%I in (1,1,80) do (
    set "DB_HEALTH="
    for /f "usebackq delims=" %%H in (`docker inspect -f "{{.State.Health.Status}}" "%CONTAINER_NAME%" 2^>nul`) do set "DB_HEALTH=%%H"
    if /I "!DB_HEALTH!"=="healthy" exit /b 0
    if /I "!DB_HEALTH!"=="unhealthy" exit /b 1
    timeout /t 2 /nobreak >nul
)
exit /b 1

:cleanup_error
if "%DB_STARTED%"=="1" (
    docker compose -f "%COMPOSE_FILE%" stop mysql >nul 2>&1
    if errorlevel 1 docker stop "%CONTAINER_NAME%" >nul 2>&1
)
goto :fatal

:fatal
echo.
echo Startup failed. No new database instance will be left running by this launcher.
echo You can also run stop_all.bat at any time to force-stop the reference database.
pause
endlocal & exit /b 1
