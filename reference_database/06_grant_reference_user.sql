-- Docker 参考数据库专用账号授权。
-- docker-compose.yml 会要求官方 MySQL 镜像创建 report_user；
-- 这里再次使用 IF NOT EXISTS 保证初始化脚本独立、稳健。

CREATE USER IF NOT EXISTS 'report_user'@'%' IDENTIFIED BY 'report123';
GRANT ALL PRIVILEGES ON production_basic_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_energy_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_operation_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_maintenance_demo.* TO 'report_user'@'%';
FLUSH PRIVILEGES;
