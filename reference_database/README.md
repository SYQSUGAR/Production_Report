# 参考数据库与数据库连接设计

## 本地测试数据库

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
字符集：utf8mb4
```

真正的 MySQL 数据文件保存在：

```text
D:\3SoftWare\mysql\production_report_demo\data
```

双击仓库根目录的 `start_all.bat` 只启动/升级数据库服务器，不启动 Python 或 PyQt。程序由用户自己的 Anaconda/IDE 环境运行。需要停止数据库时双击 `stop_all.bat`。

本地测试服务器目前提供项目数据库：

```text
production_report_demo
```

## 程序数据库使用方式

新版程序把“数据库服务器连接”和“本项目使用哪些数据库”分开。

### 数据库服务器连接配置

只保存：

```text
数据库类型
主机地址
端口
用户名
密码
字符集
```

不再在服务器连接配置中填写数据库名。

### 本项目数据库管理

服务器连接成功后，通过：

```text
数据库 → 本项目数据库管理...
```

打开双列表数据库选择器：

```text
待添加数据库  →  已添加数据库
待添加数据库  ←  已添加数据库
全部→
←全部
```

左右列表支持普通单选、Ctrl 多选和 Shift 连选；顶部搜索同时过滤两侧列表。右侧“已添加数据库”就是当前报表工程允许使用的数据范围。

数据库范围保存后，程序立即读取所有已添加数据库中的：

```text
全部数据表
全部数据表的全部字段
```

并缓存元数据。模板编辑右侧的数据库绑定按：

```text
数据库 → 数据表 → 字段
```

选择，不需要每次切换表时重新访问服务器。

如果项目只启用一个数据库，条件构建生成的 SQL 可以使用普通表名；启用多个数据库时，内部绑定保存数据库身份并生成 `database.table`。跨库出现同名表时，界面使用类似 `equipment_info (production)` 的显示方式区分，内部仍保存独立的 database/table 身份。

## production_report_demo 表

基础验证表：

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

真实项目配置表：

```text
plc_config_modbus
```

### plc_config_modbus

该表来自用户提供的 `plc_config_modbus.sql`，不是演示生成数据。当前导入：

```text
120 条真实 Modbus 点位配置
```

字段为：

```text
variable_id
variable_name
variable_en_name
biz_type
host
port
slave_id
register_address
is_active
create_by
create_time
update_by
update_time
remark
```

为便于 GitHub 维护和 BAT 分步导入，原始脚本在仓库中拆成：

```text
08a_plc_config_modbus_schema.sql   表结构
08b_plc_config_modbus_data_1.sql   数据 1/3
08c_plc_config_modbus_data_2.sql   数据 2/3
08d_plc_config_modbus_data_3.sql   数据 3/3
```

四个脚本合起来对应原始 SQL 的完整表结构和 120 条记录。

## 设备验证数据

`equipment_info` 保存设备属性，一台设备一行；`equipment_status` 严格只有：

```text
equipment_id
record_time
temperature_c
```

状态时间范围：

```text
2026-06-23 00:00:00
~
2026-06-27 23:00:00
```

每台设备 5 天 × 24 小时 = 120 条小时记录。

## 初始化脚本

```text
01_basic_data.sql                  基础资料模块
02_energy_data.sql                 能源数据模块
03_operation_data.sql              设备属性与小时状态模块
04_maintenance_data.sql            维修模块
07_unified_reference_database.sql  汇总基础验证数据到 production_report_demo
08a_plc_config_modbus_schema.sql   真实 Modbus 配置表结构
08b_plc_config_modbus_data_1.sql   真实 Modbus 配置数据 1/3
08c_plc_config_modbus_data_2.sql   真实 Modbus 配置数据 2/3
08d_plc_config_modbus_data_3.sql   真实 Modbus 配置数据 3/3
06_grant_reference_user.sql        创建/授权 report_user
00_install_all_mysql.sql           手工一键执行完整流程
```

`tools/local_launcher.ps1` 会检查：

```text
production_report_demo
设备小时状态结构
GL-03 的 120 条小时记录
plc_config_modbus 的 14 个字段
plc_config_modbus 的 120 条点位记录
```

任一项缺失时自动执行最新初始化脚本。

## 配置持久化

数据库服务器配置和本项目已选择数据库会随模板/会话保存。数据库服务器配置窗口再次打开时会回显已经保存的连接信息；数据库范围发生修改后点击“确定”立即保存并加载所有表/字段。未保存的数据库范围在关闭选择窗口时会提示“保存 / 不保存 / 取消”。

当前密码仍随模板/会话 JSON 保存为明文；正式环境后续可再迁移到系统凭据存储。

## 数据说明

2026-06-27 日报相关验证业务值主要来自此前提供的日报 Excel；设备小时温度、部分厂家型号和测试工单属于验证数据。`plc_config_modbus` 的表结构和 120 条点位记录来自本次用户提供的真实项目 SQL。

本次同时提供的 YAML 只用于确认项目环境，不纳入仓库数据库初始化脚本，也不复制其中与本程序数据库验证无关的外部服务配置或凭据。
