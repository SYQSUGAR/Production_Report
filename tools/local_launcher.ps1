$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
$MySqlHome = 'D:\3SoftWare\mysql'
$DbPort = 3307
$InstanceRoot = Join-Path $MySqlHome 'production_report_demo'
$DbData = Join-Path $InstanceRoot 'data'
$RunDir = Join-Path $InstanceRoot 'run'
$LogDir = Join-Path $InstanceRoot 'logs'
$PidFile = Join-Path $RunDir 'mysqld.pid'
$LogFile = Join-Path $LogDir 'mysql-error.log'

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

function Invoke-SqlFile([string]$MySql, [string]$RelativePath) {
    $path = Join-Path $ProjectDir $RelativePath
    if (-not (Test-Path $path)) { throw "Missing SQL file: $RelativePath" }
    $cmd = '"' + $MySql + '" --no-defaults --protocol=tcp --host=127.0.0.1 --port=' + $DbPort + ' --user=root --default-character-set=utf8mb4 < "' + $path + '"'
    cmd.exe /d /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "Failed to import: $RelativePath" }
}

try {
    Write-Host 'Production Report - Local MySQL Launcher'
    Write-Host ''

    if (-not (Test-Path $MySqlHome)) { throw "MySQL directory does not exist: $MySqlHome" }

    $mysqld = Find-Exe 'mysqld.exe'
    $mysql = Find-Exe 'mysql.exe'
    $mysqladmin = Find-Exe 'mysqladmin.exe'
    $mysqlBase = Split-Path -Parent (Split-Path -Parent $mysqld)

    New-Item -ItemType Directory -Force -Path $InstanceRoot,$DbData,$RunDir,$LogDir | Out-Null

    if (-not (Test-Path (Join-Path $DbData 'mysql'))) {
        Write-Host '[1/3] First run: initializing dedicated MySQL data directory...'
        Write-Host "      $DbData"
        & $mysqld --no-defaults --initialize-insecure "--basedir=$mysqlBase" "--datadir=$DbData"
        if ($LASTEXITCODE -ne 0) { throw 'MySQL data directory initialization failed.' }
    } else {
        Write-Host '[1/3] Existing MySQL data directory found.'
    }

    $dbAlreadyRunning = $false
    $dbPid = ''
    if (Test-Path $PidFile) {
        $dbPid = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
        if (Test-ProcessId $dbPid 'mysqld') {
            $dbAlreadyRunning = $true
        } else {
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    }

    if ($dbAlreadyRunning) {
        Write-Host "[2/3] Dedicated MySQL is already running. Reusing PID $dbPid."
    } else {
        $occupied = Get-NetTCPConnection -LocalPort $DbPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($occupied) {
            throw "Port $DbPort is already occupied by PID $($occupied.OwningProcess). For safety, nothing was killed."
        }
        Write-Host "[2/3] Starting dedicated MySQL on 127.0.0.1:$DbPort..."
        $args = @(
            '--no-defaults',
            "--basedir=$mysqlBase",
            "--datadir=$DbData",
            "--port=$DbPort",
            '--bind-address=127.0.0.1',
            "--pid-file=$PidFile",
            "--log-error=$LogFile",
            '--character-set-server=utf8mb4',
            '--collation-server=utf8mb4_unicode_ci'
        )
        Start-Process -FilePath $mysqld -ArgumentList $args -WindowStyle Hidden | Out-Null
    }

    if (-not (Wait-MySql $mysqladmin)) {
        throw "MySQL did not become ready. Check: $LogFile"
    }

    Write-Host '[3/3] Checking reference database schema and real PLC configuration...'
    $tcpArgs = Get-MySqlTcpArgs
    $dbExists = & $mysql @tcpArgs -N -B -e "SHOW DATABASES LIKE 'production_report_demo';" 2>$null
    $tableCount = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='production_report_demo';" 2>$null
    $statusColumnCount = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='production_report_demo' AND TABLE_NAME='equipment_status';" 2>$null
    $statusRequiredColumns = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='production_report_demo' AND TABLE_NAME='equipment_status' AND COLUMN_NAME IN ('equipment_id','record_time','temperature_c');" 2>$null
    $plcColumnCount = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='production_report_demo' AND TABLE_NAME='plc_config_modbus';" 2>$null
    $hourlyRows = ''
    $plcRows = ''
    if ($dbExists -eq 'production_report_demo') {
        $hourlyRows = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM production_report_demo.equipment_status WHERE equipment_id='GL-03';" 2>$null
        $plcTableExists = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='production_report_demo' AND TABLE_NAME='plc_config_modbus';" 2>$null
        if ([string]$plcTableExists -eq '1') {
            $plcRows = & $mysql @tcpArgs -N -B -e "SELECT COUNT(*) FROM production_report_demo.plc_config_modbus;" 2>$null
        }
    }

    $needsImport = ($dbExists -ne 'production_report_demo') -or
                   ([int]$tableCount -lt 10) -or
                   ([string]$statusColumnCount -ne '3') -or
                   ([string]$statusRequiredColumns -ne '3') -or
                   ([string]$hourlyRows -ne '120') -or
                   ([string]$plcColumnCount -ne '14') -or
                   ([string]$plcRows -ne '120')

    if ($needsImport) {
        Write-Host '      Initializing/upgrading reference database...'
        $scripts = @(
            'reference_database\01_basic_data.sql',
            'reference_database\02_energy_data.sql',
            'reference_database\03_operation_data.sql',
            'reference_database\04_maintenance_data.sql',
            'reference_database\07_unified_reference_database.sql',
            'reference_database\08a_plc_config_modbus_schema.sql',
            'reference_database\08b_plc_config_modbus_data_1.sql',
            'reference_database\08c_plc_config_modbus_data_2.sql',
            'reference_database\08d_plc_config_modbus_data_3.sql',
            'reference_database\06_grant_reference_user.sql'
        )
        foreach ($relative in $scripts) { Invoke-SqlFile $mysql $relative }
        Write-Host '      Reference database and PLC configuration imported successfully.'
    } else {
        Write-Host '      Current database schema and PLC configuration are complete.'
    }

    $currentPid = ''
    if (Test-Path $PidFile) {
        $currentPid = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    }

    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host 'Reference database server is running in the background.' -ForegroundColor Green
    Write-Host 'Host     : 127.0.0.1'
    Write-Host "Port     : $DbPort"
    Write-Host 'User     : report_user'
    Write-Host 'Password : report123'
    Write-Host 'Available project database: production_report_demo'
    Write-Host 'Real table: production_report_demo.plc_config_modbus (120 rows)'
    if ($currentPid) { Write-Host "PID      : $currentPid" }
    Write-Host ''
    Write-Host 'In PyQt: configure the server first, then open Project Database Management.' -ForegroundColor Yellow
    Write-Host 'Select production_report_demo there; tables and columns will be loaded automatically.' -ForegroundColor Yellow
    Write-Host 'When finished, run stop_all.bat to stop this database server.' -ForegroundColor Yellow
    Write-Host '============================================================' -ForegroundColor Green
    Start-Sleep -Seconds 5
    exit 0
}
catch {
    Write-Host ''
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No unknown MySQL process was killed.'
    Write-Host "MySQL error log: $LogFile"
    Read-Host 'Press Enter to continue'
    exit 1
}
