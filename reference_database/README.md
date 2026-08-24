# 参考数据库（仅用于验证）

本目录只保存根据用户提供的《生产运行日报（2026-06-27）》整理出的数据库建表与案例数据，**不参与程序源码运行，也不修改现有数据库连接逻辑**。

当前提供：

- `mysql_reference.sql`：MySQL 8+ 建库、建表、插入参考数据脚本。
- 数据库名：`production_report_demo`

## 使用方法

在 MySQL 中执行：

```bash
mysql -u root -p < reference_database/mysql_reference.sql
```

然后在程序原有“数据库连接配置”中填写你本机 MySQL 的地址、端口、用户名、密码，并把数据库名设置为：

```text
production_report_demo
```

再使用程序里的“刷新数据库”读取表名和字段名即可。

## 参考表

- `report_metric`：水、电、气等日值/月累计/年累计指标。
- `maintenance_record`：水维修、电维修、维修服务等计数数据。
- `equipment_runtime`：锅炉、制冷机组运行时间、压力、温度等。
- `temperature_record`：热水分区、增压站等温度数据。

这些数据只用于验证字段下拉、SQL 构建、条件筛选、时间字段和报表查询功能，不代表正式生产数据库设计。
