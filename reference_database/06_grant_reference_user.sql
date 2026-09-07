-- 生产日报本地参考数据库专用账号。
-- 最终程序只连接 production_report_demo。

SET NAMES utf8mb4;

CREATE USER IF NOT EXISTS 'report_user'@'127.0.0.1' IDENTIFIED BY 'report123';
ALTER USER 'report_user'@'127.0.0.1' IDENTIFIED BY 'report123';
GRANT ALL PRIVILEGES ON production_report_demo.* TO 'report_user'@'127.0.0.1';

CREATE USER IF NOT EXISTS 'report_user'@'localhost' IDENTIFIED BY 'report123';
ALTER USER 'report_user'@'localhost' IDENTIFIED BY 'report123';
GRANT ALL PRIVILEGES ON production_report_demo.* TO 'report_user'@'localhost';

CREATE USER IF NOT EXISTS 'report_user'@'%' IDENTIFIED BY 'report123';
ALTER USER 'report_user'@'%' IDENTIFIED BY 'report123';
GRANT ALL PRIVILEGES ON production_report_demo.* TO 'report_user'@'%';

FLUSH PRIVILEGES;
