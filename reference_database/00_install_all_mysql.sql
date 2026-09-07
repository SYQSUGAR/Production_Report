-- 一键安装统一 MySQL 参考数据库 + 真实项目 Modbus 点位配置
-- 从仓库根目录执行：
-- mysql -u root -p < reference_database/00_install_all_mysql.sql
--
-- 01~04 先生成模块验证数据，07 汇总到 production_report_demo；
-- 08a~08d 导入用户提供的 plc_config_modbus 真实结构和 120 条点位；
-- 06 最后创建/更新测试账号权限。

SOURCE reference_database/01_basic_data.sql;
SOURCE reference_database/02_energy_data.sql;
SOURCE reference_database/03_operation_data.sql;
SOURCE reference_database/04_maintenance_data.sql;
SOURCE reference_database/07_unified_reference_database.sql;
SOURCE reference_database/08a_plc_config_modbus_schema.sql;
SOURCE reference_database/08b_plc_config_modbus_data_1.sql;
SOURCE reference_database/08c_plc_config_modbus_data_2.sql;
SOURCE reference_database/08d_plc_config_modbus_data_3.sql;
SOURCE reference_database/06_grant_reference_user.sql;

USE production_report_demo;
SHOW TABLES;
SELECT COUNT(*) AS gl03_hourly_rows
FROM equipment_status
WHERE equipment_id='GL-03';
SELECT COUNT(*) AS plc_config_modbus_rows
FROM plc_config_modbus;
