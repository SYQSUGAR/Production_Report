-- 一键安装全部 MySQL 参考数据库
-- 使用方式（从仓库根目录运行）：
-- mysql -u root -p < reference_database/00_install_all_mysql.sql
--
-- SOURCE 是 MySQL 客户端命令，因此请从仓库根目录执行。

SOURCE reference_database/01_basic_data.sql;
SOURCE reference_database/02_energy_data.sql;
SOURCE reference_database/03_operation_data.sql;
SOURCE reference_database/04_maintenance_data.sql;

SHOW DATABASES LIKE 'production\_%\_demo';
