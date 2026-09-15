-- 将各模块参考库汇总为一个项目数据库。
-- 最终程序只连接 production_report_demo；四个 *_demo 模块库仅作为初始化中间产物。

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS production_report_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 按外键依赖顺序清理统一库中的旧表。
DROP TABLE IF EXISTS production_report_demo.equipment_status;
DROP TABLE IF EXISTS production_report_demo.equipment_info;
DROP TABLE IF EXISTS production_report_demo.utility_daily;
DROP TABLE IF EXISTS production_report_demo.utility_metric;
DROP TABLE IF EXISTS production_report_demo.maintenance_order;
DROP TABLE IF EXISTS production_report_demo.maintenance_daily;
DROP TABLE IF EXISTS production_report_demo.meter_point;
DROP TABLE IF EXISTS production_report_demo.team;
DROP TABLE IF EXISTS production_report_demo.location;

-- 基础资料。
CREATE TABLE production_report_demo.location LIKE production_basic_demo.location;
INSERT INTO production_report_demo.location SELECT * FROM production_basic_demo.location;

CREATE TABLE production_report_demo.team LIKE production_basic_demo.team;
INSERT INTO production_report_demo.team SELECT * FROM production_basic_demo.team;

CREATE TABLE production_report_demo.meter_point LIKE production_basic_demo.meter_point;
INSERT INTO production_report_demo.meter_point SELECT * FROM production_basic_demo.meter_point;

-- 能源数据。
CREATE TABLE production_report_demo.utility_metric LIKE production_energy_demo.utility_metric;
INSERT INTO production_report_demo.utility_metric SELECT * FROM production_energy_demo.utility_metric;

CREATE TABLE production_report_demo.utility_daily LIKE production_energy_demo.utility_daily;
INSERT INTO production_report_demo.utility_daily SELECT * FROM production_energy_demo.utility_daily;

-- 设备基本信息 + 每小时状态。
CREATE TABLE production_report_demo.equipment_info LIKE production_operation_demo.equipment_info;
INSERT INTO production_report_demo.equipment_info SELECT * FROM production_operation_demo.equipment_info;

CREATE TABLE production_report_demo.equipment_status LIKE production_operation_demo.equipment_status;
INSERT INTO production_report_demo.equipment_status SELECT * FROM production_operation_demo.equipment_status;
ALTER TABLE production_report_demo.equipment_status
  ADD CONSTRAINT fk_report_equipment_status_equipment
  FOREIGN KEY (equipment_id)
  REFERENCES production_report_demo.equipment_info(equipment_id);

-- 维修数据。
CREATE TABLE production_report_demo.maintenance_daily LIKE production_maintenance_demo.maintenance_daily;
INSERT INTO production_report_demo.maintenance_daily SELECT * FROM production_maintenance_demo.maintenance_daily;

CREATE TABLE production_report_demo.maintenance_order LIKE production_maintenance_demo.maintenance_order;
INSERT INTO production_report_demo.maintenance_order SELECT * FROM production_maintenance_demo.maintenance_order;

-- 初始化中间库已经不再需要，删除以避免 MySQL 中出现多个同项目数据库。
DROP DATABASE IF EXISTS production_basic_demo;
DROP DATABASE IF EXISTS production_energy_demo;
DROP DATABASE IF EXISTS production_operation_demo;
DROP DATABASE IF EXISTS production_maintenance_demo;

USE production_report_demo;

-- 验证：应看到 9 张业务表；GL-03 应有 120 条每小时状态记录。
SHOW TABLES;
SELECT COUNT(*) AS gl03_hourly_rows
FROM equipment_status
WHERE equipment_id='GL-03';
