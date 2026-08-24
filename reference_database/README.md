# 参考数据库（仅用于验证）

本目录只保存根据用户提供的《生产运行日报（2026-06-27）》整理出的验证数据库脚本，**不参与程序源码运行，也不修改现有数据库连接逻辑**。

为了更接近项目实际使用场景，现在提供多套独立数据库，用于验证多数据库配置、表/字段刷新、普通查询、聚合查询、关联查询、时间绑定和不同数据库类型。

## 推荐方式：Docker + 一键启动

仓库根目录已经提供：

```text
docker-compose.yml
start_all.bat
stop_all.bat
```

### 第一次使用

电脑需要安装：

- Python（并已安装项目 `requirements.txt` 中的依赖）；
- Docker Desktop。

双击：

```text
start_all.bat
```

启动器会自动完成：

1. 检查 Python 与 Docker；
2. 如果 Docker Desktop 已安装但尚未启动，会尝试启动 Docker Desktop 并等待引擎就绪；
3. 启动固定容器 `production-report-mysql`；
4. 第一次创建数据卷时，MySQL 自动执行 `01`～`04` 和 `06` 初始化脚本；
5. 等待 MySQL 健康检查通过；
6. 运行 `python main.py` 启动生产报表 PyQt 程序；
7. 正常关闭 PyQt 窗口后，BAT 自动停止 MySQL 容器，但保留数据库数据。

Docker Compose 使用固定容器名和固定数据卷，因此重复运行 `start_all.bat` **不会不断创建新的数据库实例**。下一次启动会复用原来的容器和数据。

如果程序或启动窗口异常关闭，双击：

```text
stop_all.bat
```

即可强制停止本项目的参考数据库容器。该操作不会删除数据库数据。

### Docker MySQL 连接信息

```text
数据库类型：MySQL
主机：127.0.0.1
端口：3307
用户名：report_user
密码：report123
字符集：utf8mb4
```

可分别建立 4 个连接，只修改“数据库名”：

```text
production_basic_demo
production_energy_demo
production_operation_demo
production_maintenance_demo
```

端口特意映射为 `3307`，避免与电脑上可能已经存在的本机 MySQL `3306` 冲突。

### 数据如何保存

MySQL 真正的数据保存在 Docker 命名卷：

```text
production-report-mysql-data
```

因此：

```text
docker compose stop
```

只会停止数据库，不会删除数据。再次启动时原来的库、表和记录仍然存在。

不要随意执行 `docker compose down -v` 或手动删除 `production-report-mysql-data`，除非明确希望清空测试数据库并重新初始化。

## MySQL 验证环境

### 01_basic_data.sql

创建数据库：

```text
production_basic_demo
```

主要表：

- `location`：区域、楼宇、站房等基础资料。
- `team`：锅炉运行班、制冷班、维修班等班组资料。
- `equipment`：锅炉、制冷机组等设备资料。
- `meter_point`：水、电、气、热水等计量点资料。

### 02_energy_data.sql

创建数据库：

```text
production_energy_demo
```

主要表：

- `utility_metric`：指标字典，例如供电量、耗水量、耗气量。
- `utility_daily`：各区域每日水、电、气、热水等日值/月累计/年累计数据。

2026-06-27 核心值来源于用户提供日报；2026-06-25～26 仅为时间筛选和聚合验证添加的演示数据。

### 03_operation_data.sql

创建数据库：

```text
production_operation_demo
```

主要表：

- `equipment_runtime`：锅炉、制冷机组压力、温度、运行时间和状态。
- `temperature_record`：热水分区、增压站等温度记录。

包含 `record_time` 和 `report_date` 两类时间字段，专门用于验证报表时间绑定。

### 04_maintenance_data.sql

创建数据库：

```text
production_maintenance_demo
```

主要表：

- `maintenance_daily`：日报中的水维修、电维修、维修服务日/月/年汇总。
- `maintenance_order`：演示工单明细。

工单明细为功能测试数据，可用于 LIKE、状态字段、日期时间筛选和 COUNT 聚合测试。

### 06_grant_reference_user.sql

为 Docker 自动创建的 `report_user` 授予上述四个验证数据库的访问权限。

## 手工初始化方式

如果不使用 Docker，仍然可以使用原有的一键 MySQL 脚本：

```bash
mysql -u root -p < reference_database/00_install_all_mysql.sql
```

它会创建上述 4 个 MySQL 验证数据库。

## 原单库参考脚本

`mysql_reference.sql` 仍保留，创建：

```text
production_report_demo
```

其中将日报内容集中在 4 张表中，适合快速验证单数据库场景。

## SQL Server 验证环境

`05_sqlserver_reference.sql` 创建：

```text
production_sqlserver_demo
```

包含：

- `dbo.utility_daily`
- `dbo.equipment_runtime`
- `dbo.maintenance_order`

用于验证程序原有 SQL Server 连接、字段刷新、查询和时间条件。

## 数据真实性说明

- 2026-06-27 的主要日报值来自用户提供 Excel。
- 为了验证跨日时间范围、SUM/COUNT 聚合等功能，部分脚本加入了 2026-06-25～26 的演示记录。
- `maintenance_order` 工单明细属于演示数据。

演示数据只用于软件功能验证，不代表真实生产业务记录。
