-- Docker 参考数据库专用账号授权。
-- 官方 MySQL 容器会先根据 docker-compose.yml 创建 report_user，
-- 本脚本在各业务数据库初始化完成后，为该账号授予四个测试库的访问权限。

GRANT ALL PRIVILEGES ON production_basic_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_energy_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_operation_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_maintenance_demo.* TO 'report_user'@'%';
FLUSH PRIVILEGES;
