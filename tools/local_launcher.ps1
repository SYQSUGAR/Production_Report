$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
$MySqlHome = 'D:\3SoftWare\mysql'
$DbPort = 3307
$InstanceRoot = Join-Path $MySqlHome 'production_report_demo'
$DbData = Join-Path $InstanceRoot 'data'
$RunDir = Join-Path $InstanceRoot 'run'
$LogDir = Join-Path $InstanceRoot 'logs'
$PidFile = Join-Path $RunDir 'mysqld.pid'
$AppPidFile = Join-Path $RunDir 'app.pid'
$LogFile = Join-Path $LogDir 'mysql-error.log'
$AppStdoutLog = Join-Path $LogDir 'pyqt-stdout.log'
$AppStderrLog = Join-Path $LogDir 'pyqt-stderr.log'
$CrashLog = Join-Path $HOME '.report_editor\crash.log'

function Find-Exe([string]$Name) {
    $direct = Join-Path $MySqlHome ('bin\' + $Name)
    if (Test-Path $direct) { return $direct }
    $found = Get-ChildItem -Path $MySqlHome -Filter $Name -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    throw "$Name was not found under $MySqlHome"
}

function Test-ProcessId([string]$PidText, [string]$ExpectedName = '') {
    if (-not $PidText) { return $false }
    $n = 0
    if (-not [int]::TryParse($PidText.Trim(), [ref]$n)) { return $false }
    try {
        $p = Get-Process -Id $n -ErrorAction Stop
        if ($ExpectedName -and $p.ProcessName -ne $ExpectedName) { return $false }
        return $true
    } catch { return $false }
}

function Get-MySqlTcpArgs {
    return @('--no-defaults','--protocol=tcp','--host=127.0.0.1',"--port=$DbPort",'--user=root','--default-character-set=utf8mb4')
}

function Wait-MySql([string]$MySqlAdmin) {
    $tcpArgs = Get-MySqlTcpArgs
    for ($i = 0; $i -lt 60; $i++) {
        & $MySqlAdmin @tcpArgs ping --silent 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Stop-LocalMySql([string]$MySqlAdmin) {
    $tcpArgs = Get-MySqlTcpArgs
    & $MySqlAdmin @tcpArgs shutdown 2>$null | Out-Null
    for ($i = 0; $i -lt 15; $i++) {
        if (-not (Test-Path $PidFile)) { return $true }
        $pidText = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
        if (-not (Test-ProcessId $pidText 'mysqld')) {
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Invoke-SqlFile([string]$MySql, [string]$RelativePath) {
    $path = Join-Path $ProjectDir $RelativePath
    if (-not (Test-Path $path)) { throw "Missing SQL file: $RelativePath" }
    $portArg = "--port=$DbPort"
    $cmd = '"' + $MySql + '" --no-defaults --protocol=tcp --host=127.0.0.1 ' + $portArg + ' --user=root --default-character-set=utf8mb4 < "' + $path + '"'
    cmd.exe /d /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "Failed to import: $RelativePath" }
}

function Show-AppFailure([int]$ExitCode, [double]$ElapsedSeconds) {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Red
    Write-Host 'PyQt application exited unexpectedly.' -ForegroundColor Red
    Write-Host "Exit code : $ExitCode" -ForegroundColor Red
    Write-Host ('Run time  : {0:N1} seconds' -f $ElapsedSeconds) -ForegroundColor Red

    if (Test-Path $AppStderrLog) {
        $stderrLines = Get-Content $AppStderrLog -Tail 100 -ErrorAction SilentlyContinue
        if ($stderrLines) {
            Write-Host "Python stderr: $AppStderrLog" -ForegroundColor Yellow
            Write-Host '---------------- Python stderr ----------------' -ForegroundColor Yellow
            $stderrLines | ForEach-Object { Write-Host $_ }
            Write-Host '------------------------------------------------' -ForegroundColor Yellow
        }
    }

    if (Test-Path $AppStdoutLog) {
        $stdoutLines = Get-Content $AppStdoutLog -Tail 60 -ErrorAction SilentlyContinue
        if ($stdoutLines) {
            Write-Host "Python stdout: $AppStdoutLog" -ForegroundColor Yellow
            Write-Host '---------------- Python stdout ----------------' -ForegroundColor Yellow
            $stdoutLines | ForEach-Object { Write-Host $_ }
            Write-Host '------------------------------------------------' -ForegroundColor Yellow
        }
    }

    if (Test-Path $CrashLog) {
        Write-Host "Crash log : $CrashLog" -ForegroundColor Yellow
        Write-Host '---------------- crash log --------------------' -ForegroundColor Yellow
        Get-Content $CrashLog -Tail 60 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
        Write-Host '------------------------------------------------' -ForegroundColor Yellow
    } else {
        Write-Host "No application crash log found at: $CrashLog" -ForegroundColor DarkYellow
    }

    Write-Host 'The launcher will remain open so the error can be read.' -ForegroundColor Yellow
    Write-Host '============================================================' -ForegroundColor Red
}

try {
    Write-Host 'Production Report - Local MySQL Launcher'
    Write-Host ''

    $python = $null
    foreach ($candidate in @('python','py')) {
        try {
            if ($candidate -eq 'python') {
                $value = & python -c 'import sys; print(sys.executable)' 2>$null
            } else {
                $value = & py -3 -c 'import sys; print(sys.executable)' 2>$null
            }
            if ($LASTEXITCODE -eq 0 -and $value -and (Test-Path $value.Trim())) {
                $python = $value.Trim(); break
            }
        } catch {}
    }
    if (-not $python) { throw 'Python was not found.' }
    if (-not (Test-Path $MySqlHome)) { throw "MySQL directory does not exist: $MySqlHome" }

    $mysqld = Find-Exe 'mysqld.exe'
    $mysql = Find-Exe 'mysql.exe'
    $mysqladmin = Find-Exe 'mysqladmin.exe'
    $mysqlBase = Split-Path -Parent (Split-Path -Parent $mysqld)

    New-Item -ItemType Directory -Force -Path $InstanceRoot,$DbData,$RunDir,$LogDir | Out-Null

    if (Test-Path $AppPidFile) {
        $oldApp = (Get-Content $AppPidFile -Raw -ErrorAction SilentlyContinue).Trim()
        if (Test-ProcessId $oldApp) {
            Write-Host "[INFO] Production Report is already running. PID=$oldApp"
            Write-Host 'No second application or database instance will be started.'
            Start-Sleep -Seconds 3
            exit 0
        }
        Remove-Item $AppPidFile -Force -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path (Join-Path $DbData 'mysql'))) {
        Write-Host '[1/4] First run: initializing dedicated MySQL data directory...'
        Write-Host "      $DbData"
        & $mysqld --no-defaults --initialize-insecure "--basedir=$mysqlBase" "--datadir=$DbData"
        if ($LASTEXITCODE -ne 0) { throw 'MySQL data directory initialization failed.' }
    } else {
        Write-Host '[1/4] Existing MySQL data directory found.'
    }

    $dbAlreadyRunning = $false
    if (Test-Path $PidFile) {
        $dbPid = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
        if (Test-ProcessId $dbPid 'mysqld') { $dbAlreadyRunning = $true }
        else { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    }

    if ($dbAlreadyRunning) {
        Write-Host "[2/4] Dedicated MySQL is already running. Reusing PID $dbPid."
    } else {
        $occupied = Get-NetTCPConnection -LocalPort $DbPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($occupied) { throw "Port $DbPort is already occupied by PID $($occupied.OwningProcess). For safety, nothing was killed." }
        Write-Host "[2/4] Starting dedicated MySQL on 127.0.0.1:$DbPort..."
        $args = @('--no-defaults',"--basedir=$mysqlBase","--datadir=$DbData","--port=$DbPort",'--bind-address=127.0.0.1',"--pid-file=$PidFile","--log-error=$LogFile",'--character-set-server=utf8mb4','--collation-server=utf8mb4_unicode_ci')
        Start-Process -FilePath $mysqld -ArgumentList $args -WindowStyle Hidden | Out-Null
    }

    if (-not (Wait-MySql $mysqladmin)) { throw "MySQL did not become ready. Check: $LogFile" }

    Write-Host '[3/4] Checking reference database schema...'
    $tcpArgs = Get-MySqlTcpArgs
    $basicExists = & $mysql @tcpArgs -N -B -e "SHOW DATABASES LIKE 'production_basic_demo';" 2>$null
    $statusTableExists = & $mysql @tcpArgs -N -B -e "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='production_operation_demo' AND TABLE_NAME='equipment_status';" 2>$null
    $equipmentIdType = & $mysql @tcpArgs -N -B -e "SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='production_operation_demo' AND TABLE_NAME='equipment_info' AND COLUMN_NAME='equipment_id';" 2>$null

    $needsImport = ($basicExists -ne 'production_basic_demo') -or ($statusTableExists -ne 'equipment_status') -or ($equipmentIdType -ne 'varchar')
    if ($needsImport) {
        Write-Host '      Initializing/upgrading reference database schema...'
        $scripts = @(
            'reference_database\01_basic_data.sql',
            'reference_database\02_energy_data.sql',
            'reference_database\03_operation_data.sql',
            'reference_database\04_maintenance_data.sql',
            'reference_database\06_grant_reference_user.sql'
        )
        foreach ($relative in $scripts) { Invoke-SqlFile $mysql $relative }
        Write-Host '      Reference databases initialized/upgraded successfully.'
    } else {
        Write-Host '      Current reference database schema found. No re-import needed.'
    }

    Write-Host ''
    Write-Host 'Reference database is ready.'
    Write-Host 'Host     : 127.0.0.1'
    Write-Host "Port     : $DbPort"
    Write-Host 'User     : report_user'
    Write-Host 'Password : report123'
    Write-Host 'Databases: production_basic_demo / production_energy_demo / production_operation_demo / production_maintenance_demo'
    Write-Host ''
    Write-Host '[4/4] Starting PyQt application...'
    Write-Host 'Close the PyQt window normally to stop this dedicated MySQL instance.'

    Remove-Item $AppStdoutLog,$AppStderrLog -Force -ErrorAction SilentlyContinue
    $startedAt = Get-Date
    $app = Start-Process -FilePath $python -ArgumentList 'main.py' -WorkingDirectory $ProjectDir -RedirectStandardOutput $AppStdoutLog -RedirectStandardError $AppStderrLog -PassThru
    Set-Content -Path $AppPidFile -Value $app.Id -Encoding ascii
    $app.WaitForExit()
    $appExit = $app.ExitCode
    $elapsed = ((Get-Date) - $startedAt).TotalSeconds
    Remove-Item $AppPidFile -Force -ErrorAction SilentlyContinue

    $suspiciousExit = ($appExit -ne 0) -or ($elapsed -lt 3)
    if ($suspiciousExit) {
        Show-AppFailure $appExit $elapsed
    }

    Write-Host ''
    Write-Host 'Application closed. Stopping dedicated MySQL instance...'
    if (Stop-LocalMySql $mysqladmin) {
        Write-Host "Database stopped. Saved data is preserved in: $DbData"
    } else {
        Write-Warning 'Normal shutdown did not finish. Run stop_all.bat to force-stop only this project instance.'
    }

    if ($suspiciousExit) {
        Read-Host 'Press Enter after you have copied or photographed the error above'
    }
    exit $appExit
}
catch {
    Write-Host ''
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Startup failed. No unknown MySQL process was killed.'
    Write-Host 'If the dedicated test instance remains running, use stop_all.bat.'
    if (Test-Path $CrashLog) {
        Write-Host "Crash log: $CrashLog" -ForegroundColor Yellow
    }
    Read-Host 'Press Enter to continue'
    exit 1
}
