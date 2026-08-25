-- 一键安装统一 MySQL 参考数据库
-- 从仓库根目录执行：
-- mysql -u root -p < reference_database/00_install_all_mysql.sql
--
-- 01~04 先生成模块数据，07 汇总到 production_report_demo，
-- 06 最后创建/更新测试账号权限。

SOURCE reference_database/01_basic_data.sql;
SOURCE reference_database/02_energy_data.sql;
SOURCE reference_database/03_operation_data.sql;
SOURCE reference_database/04_maintenance_data.sql;
SOURCE reference_database/07_unified_reference_database.sql;
SOURCE reference_database/06_grant_reference_user.sql;

USE production_report_demo;
SHOW TABLES;
SELECT COUNT(*) AS gl03_hourly_rows
FROM equipment_status
WHERE equipment_id='GL-03';
