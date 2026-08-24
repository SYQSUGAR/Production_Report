# 参考数据库（仅用于验证）

本目录只保存根据用户提供的《生产运行日报（2026-06-27）》整理出的验证数据库脚本，**不参与程序源码运行，也不修改现有数据库连接逻辑**。

为了更接近项目实际使用场景，现在不再只有一个演示数据库，而是提供多套独立数据库，用于验证多数据库配置、表/字段刷新、普通查询、聚合查询、关联查询、时间绑定和不同数据库类型。

## MySQL 验证环境

### 00_install_all_mysql.sql

一次创建全部 MySQL 验证数据库。

从仓库根目录执行：

```bash
mysql -u root -p < reference_database/00_install_all_mysql.sql
```

它会依次执行下面 4 个脚本。

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

适合验证基础数据类查询、表名/字段下拉和关联条件。

### 02_energy_data.sql

创建数据库：

```text
production_energy_demo
```

主要表：

- `utility_metric`：指标字典，例如供电量、耗水量、耗气量。
- `utility_daily`：各区域每日水、电、气、热水等日值/月累计/年累计数据。

2026-06-27 核心值来源于用户提供日报；2026-06-25～26 仅为时间筛选和聚合验证添加的演示数据。

适合验证：

- 普通单值查询；
- SUM 等聚合；
- 日期条件；
- `utility_daily` 与 `utility_metric` 的 JOIN；
- `updated_at` 时间字段绑定。

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

工单明细为功能测试数据，用于验证：

- `LIKE` 文本筛选；
- 状态字段；
- 日期时间筛选；
- COUNT 聚合；
- 中文字段内容查询。

## 原单库参考脚本

`mysql_reference.sql` 仍保留，创建：

```text
production_report_demo
```

其中将日报内容集中在 4 张表中，适合快速验证，不需要配置多个数据库连接。

## SQL Server 验证环境

### 05_sqlserver_reference.sql

创建数据库：

```text
production_sqlserver_demo
```

包含：

- `dbo.utility_daily`
- `dbo.equipment_runtime`
- `dbo.maintenance_order`

用于验证程序原有 SQL Server 连接、字段刷新、查询和时间条件。

可在 SQL Server Management Studio 中打开并执行该脚本。

## 推荐的程序数据库连接配置

为了测试模板同时使用多个数据库，可以在程序中分别建立类似以下连接项：

```text
基础资料库      -> production_basic_demo
能源数据库      -> production_energy_demo
设备运行库      -> production_operation_demo
维修数据库      -> production_maintenance_demo
```

如果要验证 SQL Server，再增加：

```text
SQLServer测试库 -> production_sqlserver_demo
```

这些数据库可以使用同一台本机 MySQL 服务，只是数据库名称不同。这样最适合验证当前模板中不同单元格绑定不同 `db_config_key` 的情况。

## 数据真实性说明

- 2026-06-27 的主要日报值来自用户提供 Excel。
- 为了验证跨日时间范围、SUM/COUNT 聚合等功能，部分脚本加入了 2026-06-25～26 的演示记录。
- `maintenance_order` 工单明细同样属于演示数据。

演示数据只用于软件功能验证，不代表真实生产业务记录。
