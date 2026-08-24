# 长庆油田生产运行日报参考案例

本目录只保存**案例数据与模板绑定方案**，不属于主程序运行逻辑，也不会被 `main.py` 自动导入。

## 1. 数据关系

正确的数据链路是：

```text
小时级/事件级原始数据
        ↓
模板单元格 QueryBinding
        ↓
SUM / COUNT / AVG + 日/月/年时间范围
        ↓
报表预览
        ↓
《生产运行日报（2026-06-27）》最终结果
```

Excel 中的“日供、月累、年累、日维修、月累、年累”等结果不是数据库原始字段。

## 2. 参考数据库表

### `cq_hourly_metric`

水、电、气、热水、补水等**每小时增量**。

主要字段：

- `record_time`
- `location_name`
- `metric_code`
- `metric_name`
- `unit`
- `metric_value`

日报中的日/月/年值均对 `metric_value` 做 `SUM`，区别只在时间范围。

### `cq_equipment_hourly`

锅炉、制冷机组每小时运行记录：

- `record_time`
- `team_name`
- `equipment_name`
- `pressure_mpa`
- `supply_temp_c`
- `return_temp_c`
- `runtime_hours`

运行时间使用 `SUM(runtime_hours)`；压力和温度案例使用日范围 `AVG`。

### `cq_temperature_hourly`

热水分区、增压站等每小时温度采样：

- `record_time`
- `location_name`
- `temperature_type`
- `temperature_c`

### `cq_maintenance_event`

水维修、电维修、维修服务等人工业务事件：

- `event_time`
- `location_name`
- `category`
- `description`

日报中的日/月/年维修数量通过 `COUNT(event_id)` 集计，而不是每天直接存三个汇总数。

## 3. 参考数据说明

用户提供的 Excel 只包含 2026-06-27 的最终日报结果，没有真实小时历史数据。

因此 `generate_reference_database.py` 会把：

- 2026-01-01～2026-05-31 对应“年累 - 月累”；
- 2026-06-01～2026-06-26 对应“月累 - 当日”；
- 2026-06-27 对应“当日”；

按照确定性的小时权重拆分成演示明细，使再次按照日/月/年集计时与 Excel 最终值一致。

这些小时值是**构造的参考案例数据**，不能当作长庆油田真实历史采集数据。

## 4. 生成参考数据库

脚本支持项目本来就支持的 MySQL / SQL Server，不要求主程序增加新的数据库类型。

MySQL 示例：

```bash
python examples/changqing_reference/generate_reference_database.py \
  --db-type mysql \
  --host 127.0.0.1 \
  --port 3306 \
  --user root \
  --password YOUR_PASSWORD \
  --database production_report_demo
```

SQL Server 示例：

```bash
python examples/changqing_reference/generate_reference_database.py \
  --db-type sqlserver \
  --host 127.0.0.1 \
  --port 1433 \
  --user sa \
  --password YOUR_PASSWORD \
  --database production_report_demo
```

## 5. 模板绑定

`binding_plan.py` 只配置模板单元格的：

- 数据表；
- 返回字段；
- SUM / COUNT / AVG；
- 筛选条件；
- 时间字段；
- 日 / 月 / 年时间范围。

没有把 SQL 字符串写死进主程序。

例如 Excel 的兴隆园小区供电量：

- D6：`SUM(metric_value)` + 日范围；
- E6：同一字段 + 月范围；
- F6：同一字段 + 年范围；
- 过滤条件：`location_name=兴隆园小区`、`metric_code=electricity_supply`。

程序仍然通过已有 QueryBinding 构建器动态生成 SQL。

## 6. 当前长庆油田预设的位置问题

当前 GitHub 分支的 `templates/presets.py` 只包含三个内置预设：

- 供水生产运行日报
- 供电生产运行日报
- 维修生产运行日报

仓库中没有“长庆油田”内置预设文件。

如果软件界面中已经存在“长庆油田”预设，它属于用户本机保存的自定义预设，通常位于：

```text
C:\Users\<用户名>\.report_editor\presets\
```

要把 `binding_plan.py` 真正写入这个现有预设，需要先把该预设 JSON 导出或提供出来。

拿到 JSON 后可以直接执行：

```bash
python examples/changqing_reference/binding_plan.py 原模板.json 输出模板.json
```

该操作只替换对应数据单元格的 `query_binding`，不会修改原模板的文字、字体、颜色、边框、合并、行高和列宽。
