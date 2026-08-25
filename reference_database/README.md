# 参考数据库（仅用于验证）

本目录只保存根据用户提供的《生产运行日报（2026-06-27）》整理出的验证数据库脚本，**不参与程序源码运行，也不修改现有数据库连接逻辑**。

当前推荐方式是不使用 Docker，直接复用电脑上已有的 MySQL：

```text
D:\3SoftWare\mysql
```

仓库根目录提供 `start_all.bat` 和 `stop_all.bat`。启动器会使用 `127.0.0.1:3307` 启动本项目专用 MySQL，并把真实数据保存在：

```text
D:\3SoftWare\mysql\production_report_demo\data
```

程序连接信息：

```text
数据库类型：MySQL
主机：127.0.0.1
端口：3307
用户名：report_user
密码：report123
字符集：utf8mb4
```

当前测试数据库包括：

```text
production_basic_demo
production_energy_demo
production_operation_demo
production_maintenance_demo
```

## 设备运行数据库结构

`03_operation_data.sql` 创建 `production_operation_demo`。设备数据现在严格拆成“设备属性”和“设备状态”两类。

### equipment_info

设备属性表，一台设备只保存一行：

```text
equipment_id        设备ID/业务编号，例如 GL-03
equipment_name      设备名称，例如 3#锅炉
equipment_type      设备类型
team_name           所属班组
location_name       安装位置
manufacturer        厂家
model               型号
rated_power_kw      额定功率
install_date        安装日期
enabled             是否启用
remark              其他设备信息
```

`equipment_id` 直接使用业务设备编号，不再另外设置一套自增数字 ID。

### equipment_status

设备状态表严格只有三列：

```text
equipment_id        设备ID，关联 equipment_info.equipment_id
record_time         记录时间，颗粒度为 1 小时
temperature_c       设备温度（°C）
```

主键为：

```text
(equipment_id, record_time)
```

因此同一设备在同一个整点只能存在一条状态记录。

状态表不保存设备名称、类型、班组、位置等重复信息。需要设备名称时通过 `equipment_id` JOIN：

```sql
SELECT
    e.equipment_id,
    e.equipment_name,
    e.equipment_type,
    s.record_time,
    s.temperature_c
FROM equipment_info e
JOIN equipment_status s
  ON s.equipment_id = e.equipment_id
WHERE e.equipment_id = 'GL-03'
ORDER BY s.record_time;
```

## 5 天小时状态数据

当前演示状态时间范围为：

```text
2026-06-23 00:00:00
到
2026-06-27 23:00:00
```

按每小时一条记录计算：

```text
5 天 × 24 小时 = 每台设备 120 条状态记录
```

例如 `GL-03`（3#锅炉）会有：

```text
GL-03 | 2026-06-23 00:00:00 | 温度
GL-03 | 2026-06-23 01:00:00 | 温度
GL-03 | 2026-06-23 02:00:00 | 温度
...
GL-03 | 2026-06-27 23:00:00 | 温度
```

这些温度数据是为时间筛选、JOIN、小时级查询和报表绑定生成的演示数据，不代表 Excel 中的真实设备温度。

## 自动结构升级

`tools/local_launcher.ps1` 会检查设备状态表是否满足：

```text
equipment_status 总列数 = 3
必须存在 equipment_id / record_time / temperature_c
GL-03 的小时记录数 = 120
```

如果你电脑上的测试数据库还是旧结构，下一次执行 `start_all.bat` 时会自动重新执行最新 SQL，把设备运行库升级为当前结构。

## 其他数据库

`01_basic_data.sql`：公共基础资料，例如区域、班组、计量点。

`02_energy_data.sql`：水、电、气等能源日报测试数据。

`04_maintenance_data.sql`：维修日报和维修工单测试数据。

`06_grant_reference_user.sql`：创建/授权测试用户 `report_user / report123`。

`mysql_reference.sql`：旧的单数据库快速验证版本。

`05_sqlserver_reference.sql`：SQL Server 验证版本。

## 数据真实性说明

2026-06-27 日报相关业务值主要来源于用户提供的 Excel。为验证软件功能而增加的设备温度、厂家、型号、工单明细和跨时段记录均属于演示数据，不代表真实生产记录。
