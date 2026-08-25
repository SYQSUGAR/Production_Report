# 参考数据库（仅用于验证）

本目录只保存根据用户提供的《生产运行日报（2026-06-27）》整理出的验证数据库脚本，**不参与程序源码运行，也不修改现有数据库连接逻辑**。

当前推荐方式是不使用 Docker，直接复用电脑上已有的 MySQL 程序：

```text
D:\3SoftWare\mysql
```

仓库根目录提供：

```text
start_all.bat
stop_all.bat
```

## 一键启动

双击：

```text
start_all.bat
```

启动器会检查 Python 和 MySQL，在 `D:\3SoftWare\mysql\production_report_demo\data` 使用独立数据目录，以 `127.0.0.1:3307` 启动本项目专用 MySQL。第一次启动或检测到旧版参考数据库结构时，会自动执行最新 SQL 脚本进行初始化/升级，然后启动 `main.py`。正常关闭 PyQt 后，启动器会自动关闭该测试 MySQL，但保留数据目录。

## 防止重复启动

固定配置：

```text
端口：3307
MySQL PID：D:\3SoftWare\mysql\production_report_demo\run\mysqld.pid
程序 PID：D:\3SoftWare\mysql\production_report_demo\run\app.pid
数据目录：D:\3SoftWare\mysql\production_report_demo\data
```

因此再次运行 `start_all.bat` 时，如果 PyQt 已经运行，不会打开第二个程序；如果本项目 MySQL 已经运行，会复用原实例；如果 3307 被未知程序占用，会报错退出，不会误杀未知进程。

## 一键停止

正常情况下直接关闭 PyQt 窗口即可。异常情况下双击：

```text
stop_all.bat
```

脚本只根据本项目记录的 PID 停止 PyQt 和 3307 测试 MySQL，不使用 `taskkill /IM mysqld.exe`，不会影响电脑上其他 MySQL 服务。

## 程序连接信息

```text
数据库类型：MySQL
主机：127.0.0.1
端口：3307
用户名：report_user
密码：report123
字符集：utf8mb4
```

数据库名：

```text
production_basic_demo
production_energy_demo
production_operation_demo
production_maintenance_demo
```

## 数据保存方式

真正的数据保存在：

```text
D:\3SoftWare\mysql\production_report_demo\data
```

`.sql` 文件主要用于首次初始化、结构升级和重新建立测试数据。

## MySQL 验证脚本

### 01_basic_data.sql

创建 `production_basic_demo`，主要保存公共基础资料：

- `location`：区域/楼宇/站房；
- `team`：班组；
- `meter_point`：水、电、气、热水计量点。

设备主数据不再重复保存在这里，统一放到设备运行库。

### 02_energy_data.sql

创建 `production_energy_demo`：

- `utility_metric`
- `utility_daily`

2026-06-27 核心值来源于用户提供日报；2026-06-25～26 为时间筛选和聚合验证添加的演示数据。

### 03_operation_data.sql

创建 `production_operation_demo`，核心采用标准“主数据 + 时序状态”结构：

```text
equipment_info       设备基本信息，一台设备只有一行
    equipment_id PK
    equipment_code
    equipment_name
    equipment_type
    team_name
    location_name
    manufacturer
    model
    rated_power_kw
    install_date
    ...

        1
        │ equipment_id
        │
        N

equipment_status     设备状态/历史数据，同一设备可有很多行
    status_id PK
    equipment_id FK
    record_time
    report_date
    pressure_mpa
    supply_temp_c
    return_temp_c
    runtime_hours
    month_runtime_hours
    year_runtime_hours
    running_status
```

例如 `3#锅炉` 的名称、类型、班组等只在 `equipment_info` 保存一次；2026-06-25、26、27 的压力、温度、运行时间分别作为多条 `equipment_status` 记录，并使用同一个 `equipment_id` 关联。

因此查询“3#锅炉在 2026-06-27 的压力”时，可以真实验证 JOIN：

```sql
SELECT e.equipment_name, s.record_time, s.pressure_mpa
FROM equipment_info e
JOIN equipment_status s ON s.equipment_id = e.equipment_id
WHERE e.equipment_code = 'GL-03'
  AND s.record_time >= '2026-06-27 00:00:00'
  AND s.record_time < '2026-06-28 00:00:00';
```

另外保留 `temperature_record` 用于区域温度时序数据测试。

### 04_maintenance_data.sql

创建 `production_maintenance_demo`：

- `maintenance_daily`
- `maintenance_order`

### 06_grant_reference_user.sql

创建/更新测试账号：

```text
report_user / report123
```

并授予四个测试库访问权限。

## 其他保留脚本

`mysql_reference.sql`：旧的单数据库快速验证版本。

`05_sqlserver_reference.sql`：SQL Server 验证版本。

`00_install_all_mysql.sql`：手工导入多库环境时使用。

## 数据真实性说明

- 2026-06-27 的主要日报值来自用户提供 Excel；
- 2026-06-25～26 的部分记录用于测试跨日、JOIN 和聚合；
- 设备厂家、型号等缺少原始来源的字段属于明确的演示基础信息；
- `maintenance_order` 工单明细属于演示数据。

演示数据只用于软件功能验证，不代表真实生产业务记录。
