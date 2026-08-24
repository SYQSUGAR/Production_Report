# 数据库目录

本目录包含数据库访问代码和一个基于《生产运行日报（2026-06-27）》整理的本地 SQLite 参考数据库生成器。

## 示例数据库结构

示例数据库不以二进制 `.db` 文件提交到 GitHub，而是在本地运行时生成，避免仓库保存机器相关文件。

### `report_metric`
用于水、电、气、补水量等日/月/年累计指标。

主要字段：
- `report_date`：日报日期
- `location_name`：区域、楼宇或班组
- `metric_code`：程序使用的指标编码
- `metric_name`：中文指标名称
- `unit`：单位
- `daily_value`：日值
- `month_total`：月累计
- `year_total`：年累计

### `maintenance_record`
用于水维修、电维修、维修服务等计数型数据。

### `equipment_runtime`
用于锅炉、制冷机组等设备运行信息，包括压力、出回水温度和运行时长。

### `temperature_record`
用于热水分区、增压站等温度记录。

## 参考查询

```sql
SELECT daily_value
FROM report_metric
WHERE report_date = '2026-06-27'
  AND location_name = '兴隆园小区'
  AND metric_code = 'electricity_supply';
```

```sql
SELECT year_runtime_hours
FROM equipment_runtime
WHERE report_date = '2026-06-27'
  AND team_name = '锅炉运行班'
  AND equipment_name = '3#锅炉';
```

```sql
SELECT daily_count
FROM maintenance_record
WHERE report_date = '2026-06-27'
  AND category = '水维修（公建）';
```

## 生成示例库

```bash
python -m database.sample_database
```

默认生成到：

```text
~/.report_editor/sample_production_report.db
```

该库仅用于程序开发、字段下拉和查询绑定演示，不代表正式生产数据库设计。
