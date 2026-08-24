@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Production Report - Stop Reference Database

set "COMPOSE_FILE=%~dp0docker-compose.yml"
set "CONTAINER_NAME=production-report-mysql"

echo Stopping Production Report reference database...

where docker >nul 2>&1
if errorlevel 1 (
    echo Docker command was not found. There is no Docker database process this script can stop.
    pause
    endlocal & exit /b 1
)

docker compose -f "%COMPOSE_FILE%" stop mysql >nul 2>&1
if errorlevel 1 docker stop "%CONTAINER_NAME%" >nul 2>&1

for /f "usebackq delims=" %%S in (`docker inspect -f "{{.State.Running}}" "%CONTAINER_NAME%" 2^>nul`) do set "RUNNING=%%S"
if /I "%RUNNING%"=="true" (
    echo [ERROR] The database container is still running.
    echo Open Docker Desktop and stop container: %CONTAINER_NAME%
    pause
    endlocal & exit /b 1
)

echo Database stopped.
echo The saved database data is NOT deleted; the next start will reuse the same data.
timeout /t 2 /nobreak >nul
endlocal & exit /b 0
