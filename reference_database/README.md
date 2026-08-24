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

启动器会：

1. 检查 Python；
2. 在 `D:\3SoftWare\mysql` 下寻找 `mysqld.exe`、`mysql.exe`、`mysqladmin.exe`；
3. 为本项目创建独立数据目录 `D:\3SoftWare\mysql\production_report_demo\data`；
4. 使用固定端口 `127.0.0.1:3307` 启动独立 MySQL 测试实例，不影响电脑上可能已经运行的 3306 MySQL 服务；
5. 第一次启动时自动执行 `01`～`04` 和 `06` SQL 脚本，创建测试库、表和数据；
6. 启动 `main.py`；
7. 正常关闭 PyQt 程序后，自动正常关闭该测试 MySQL 实例，但保留数据目录。

## 防止重复启动

该启动器使用固定：

```text
端口：3307
MySQL PID：D:\3SoftWare\mysql\production_report_demo\run\mysqld.pid
程序 PID：D:\3SoftWare\mysql\production_report_demo\run\app.pid
数据目录：D:\3SoftWare\mysql\production_report_demo\data
```

因此再次双击 `start_all.bat` 时：

- 如果 PyQt 程序已经在运行，不会再打开第二个程序；
- 如果本项目 MySQL 已经在运行，会复用原实例，不会启动第二个数据库；
- 如果 3307 被未知程序占用，会直接报错并退出，不会误杀未知数据库。

## 一键停止

正常情况下直接关闭 PyQt 窗口即可，`start_all.bat` 会随后自动关闭测试数据库。

如果程序异常、BAT 窗口被关闭，或者想手动全部停止，双击：

```text
stop_all.bat
```

它会先按 `app.pid` 停止本项目 PyQt 程序，再使用 `mysqladmin shutdown` 正常关闭 3307 测试库；只有正常关闭失败时，才会根据本项目自己的 `mysqld.pid` 强制结束该 PID。

**脚本不会使用 `taskkill /IM mysqld.exe`，因此不会把电脑上其他 MySQL 服务一起杀掉。**

## 程序连接信息

```text
数据库类型：MySQL
主机：127.0.0.1
端口：3307
用户名：report_user
密码：report123
字符集：utf8mb4
```

分别建立 4 个数据库连接时，只修改数据库名：

```text
production_basic_demo
production_energy_demo
production_operation_demo
production_maintenance_demo
```

## 数据保存方式

真正的数据不在 `.sql` 文件中持续运行，而保存在：

```text
D:\3SoftWare\mysql\production_report_demo\data
```

`.sql` 文件主要用于第一次初始化和以后需要重新建立测试数据时使用。停止数据库或关闭电脑不会删除数据，下次启动仍读取原来的数据目录。

## MySQL 验证脚本

### 01_basic_data.sql

创建 `production_basic_demo`，主要包含：

- `location`
- `team`
- `equipment`
- `meter_point`

### 02_energy_data.sql

创建 `production_energy_demo`，主要包含：

- `utility_metric`
- `utility_daily`

2026-06-27 核心值来源于用户提供日报；2026-06-25～26 为时间筛选和聚合验证添加的演示数据。

### 03_operation_data.sql

创建 `production_operation_demo`，主要包含：

- `equipment_runtime`
- `temperature_record`

包含 `record_time` 和 `report_date` 两类时间字段。

### 04_maintenance_data.sql

创建 `production_maintenance_demo`，主要包含：

- `maintenance_daily`
- `maintenance_order`

### 06_grant_reference_user.sql

创建/更新本测试实例专用账号：

```text
report_user / report123
```

并授予上述四个测试库访问权限。

## 其他保留脚本

`mysql_reference.sql`：单数据库快速验证版本，创建 `production_report_demo`。

`05_sqlserver_reference.sql`：SQL Server 验证版本，创建 `production_sqlserver_demo`。

`00_install_all_mysql.sql`：如果以后想手工导入到另一套 MySQL 服务，可继续使用。

## 数据真实性说明

- 2026-06-27 的主要日报值来自用户提供 Excel；
- 2026-06-25～26 的部分记录用于测试跨日和聚合；
- `maintenance_order` 工单明细属于演示数据。

演示数据只用于软件功能验证，不代表真实生产业务记录。
