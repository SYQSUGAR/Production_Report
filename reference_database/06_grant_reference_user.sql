-- 生产日报本地参考数据库专用账号。
-- 由 start_all.bat 在首次初始化四个测试库后执行。
-- 与 Docker 无关，不修改电脑上其他 MySQL 实例的账号。

CREATE USER IF NOT EXISTS 'report_user'@'%' IDENTIFIED BY 'report123';
ALTER USER 'report_user'@'%' IDENTIFIED BY 'report123';
GRANT ALL PRIVILEGES ON production_basic_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_energy_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_operation_demo.* TO 'report_user'@'%';
GRANT ALL PRIVILEGES ON production_maintenance_demo.* TO 'report_user'@'%';
FLUSH PRIVILEGES;
