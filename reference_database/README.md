# 参考数据库（仅用于验证）

当前参考环境统一使用一个项目数据库：

```text
production_report_demo
```

MySQL 程序位置：

```text
D:\3SoftWare\mysql
```

项目专用实例：

```text
主机：127.0.0.1
端口：3307
用户名：report_user
密码：report123
数据库名：production_report_demo
字符集：utf8mb4
```

真正的 MySQL 数据文件保存在：

```text
D:\3SoftWare\mysql\production_report_demo\data
```

双击仓库根目录的 `start_all.bat` 只启动数据库；程序 `main.py` 由用户自己的 Anaconda/IDE 环境启动。需要停止数据库时双击 `stop_all.bat`。

## 为什么改成一个数据库

当前 PyQt 程序界面只有一个全局 `default` 数据库连接配置，因此参考环境也统一成一个项目数据库最合适。一个连接即可读取全部业务表，也方便直接 JOIN。

最终 `production_report_demo` 主要包含：

```text
location
team
meter_point
utility_metric
utility_daily
equipment_info
equipment_status
maintenance_daily
maintenance_order
```

01～04 SQL 仍作为模块化初始化脚本使用；`07_unified_reference_database.sql` 会把这些模块表汇总进 `production_report_demo`，随后删除初始化过程中产生的四个临时模块库。

## 设备数据结构

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

### equipment_status

设备状态表严格只有三列：

```text
equipment_id        设备ID，关联 equipment_info.equipment_id
record_time         记录时间，颗粒度 1 小时
temperature_c       设备温度（°C）
```

主键：

```text
(equipment_id, record_time)
```

状态时间范围：

```text
2026-06-23 00:00:00
~
2026-06-27 23:00:00
```

每台设备：

```text
5 天 × 24 小时 = 120 条状态记录
```

查询设备名称与状态时通过 `equipment_id` JOIN：

```sql
SELECT
    e.equipment_id,
    e.equipment_name,
    s.record_time,
    s.temperature_c
FROM equipment_info e
JOIN equipment_status s
  ON s.equipment_id = e.equipment_id
WHERE e.equipment_id = 'GL-03'
ORDER BY s.record_time;
```

## 初始化脚本

```text
01_basic_data.sql               基础资料模块
02_energy_data.sql              能源数据模块
03_operation_data.sql           设备属性与小时状态模块
04_maintenance_data.sql         维修数据模块
07_unified_reference_database.sql  汇总为 production_report_demo
06_grant_reference_user.sql     创建/授权 report_user
00_install_all_mysql.sql        手工一键执行上述流程
```

`tools/local_launcher.ps1` 会自动检查统一库、表结构以及 `GL-03` 的 120 条小时记录。发现旧结构时会自动重新初始化并汇总。

## 程序中的数据库配置保存

程序的 `DbConfig` 会随模板序列化到 `db_configs`，并在关闭程序时保存到：

```text
~/.report_editor/last_session.json
```

当前分支还增加了数据库连接配置回显与立即保存：点击配置窗口“确定”后会立即更新当前会话，再次打开配置窗口会显示上一次填写的 host、port、用户名、密码、数据库名和字符集。

注意：现有设计中的数据库密码会以明文写入模板/会话 JSON。当前参考环境仅用于本机测试；正式环境后续应考虑 Windows Credential Manager、keyring 或其它安全凭据存储方式。

## 数据真实性说明

2026-06-27 日报相关业务值主要来源于用户提供的 Excel。为验证软件功能而增加的设备温度、厂家、型号、工单明细和跨时段记录均属于演示数据，不代表真实生产记录。
