-- 生产运行日报参考数据库（MySQL 8+）
-- 数据来源：用户提供《生产运行日报（2026-06-27）》；仅用于功能验证。

CREATE DATABASE IF NOT EXISTS production_report_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_report_demo;

DROP TABLE IF EXISTS temperature_record;
DROP TABLE IF EXISTS equipment_runtime;
DROP TABLE IF EXISTS maintenance_record;
DROP TABLE IF EXISTS report_metric;

CREATE TABLE report_metric (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  metric_code VARCHAR(64) NOT NULL,
  metric_name VARCHAR(100) NOT NULL,
  unit VARCHAR(32),
  daily_value DECIMAL(18,3),
  month_total DECIMAL(18,3),
  year_total DECIMAL(18,3),
  UNIQUE KEY uk_metric (report_date, location_name, metric_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE maintenance_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  category VARCHAR(100) NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  daily_count INT,
  month_total INT,
  year_total INT,
  description VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE equipment_runtime (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  team_name VARCHAR(100) NOT NULL,
  equipment_name VARCHAR(100) NOT NULL,
  pressure_mpa DECIMAL(10,3),
  supply_temp_c DECIMAL(10,2),
  return_temp_c DECIMAL(10,2),
  runtime_hours DECIMAL(12,2),
  month_runtime_hours DECIMAL(12,2),
  year_runtime_hours DECIMAL(12,2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE temperature_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  temperature_type VARCHAR(100) NOT NULL,
  temperature_c DECIMAL(10,2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO report_metric
(report_date, location_name, metric_code, metric_name, unit, daily_value, month_total, year_total) VALUES
('2026-06-27','兴隆园小区','water_supply','供水量','m3',0,18660,126910),
('2026-06-27','兴隆园小区','electricity_supply','供电量','Kwh',87000,2429000,16235774),
('2026-06-27','兴隆园小区','industrial_gas','工业耗气量','m3',1590,59219,1191208),
('2026-06-27','长庆综合科研楼','water_use','耗水量','m3',0,0,0),
('2026-06-27','长庆综合科研楼','electricity_use','耗电量','Kwh',17385,528000,3342335),
('2026-06-27','长庆大厦','water_use','耗水量','m3',9,941,4253),
('2026-06-27','长庆大厦','electricity_use','耗电量','Kwh',12960,370620,1699925),
('2026-06-27','苏里格大厦','water_use','耗水量','m3',32,3345,14290),
('2026-06-27','苏里格大厦','electricity_use','耗电量','Kwh',10960,368640,2194220),
('2026-06-27','长庆科技大厦','water_use','耗水量','m3',27,577,3967),
('2026-06-27','长庆科技大厦','electricity_use','耗电量','Kwh',5440,286120,1844800),
('2026-06-27','明光路办公区','water_use','耗水量','m3',103,3592,16665),
('2026-06-27','明光路办公区','electricity_use','耗电量','Kwh',6210,248850,1283470),
('2026-06-27','长实大厦','electricity_supply','供电量','Kwh',6300,162700,1033980),
('2026-06-27','换热站','electricity_use','换热站耗电量','Kwh',240,6960,62680),
('2026-06-27','锅炉房','electricity_use','锅炉房耗电量','Kwh',593.6,15358.4,162019.7),
('2026-06-27','锅炉房','gas_use','耗气量','Nm3',1590,48678,300186),
('2026-06-27','锅炉房','hot_water_use','卫生热水耗量','m3',523,12970,89289),
('2026-06-27','锅炉房','makeup_water','补水量','m3',0.2,5.4,35.2),
('2026-06-27','增压站三区','electricity_use','三区耗电量','Kwh',1480,43123,358097),
('2026-06-27','科研楼制冷班','water_use','耗水量','m3',0,118,1446),
('2026-06-27','科研楼制冷班','electricity_use','耗电量','Kwh',0,5603,180572),
('2026-06-27','科研楼制冷班','gas_use','耗气量','m3',0,2694,276246),
('2026-06-27','大厦制冷班','water_use','耗水量','m3',0,90,1580),
('2026-06-27','大厦制冷班','electricity_use','耗电量','Kwh',0,6614,254243),
('2026-06-27','大厦制冷班','gas_use','耗气量','m3',0,3047,287247),
('2026-06-27','明光路制冷班','water_use','耗水量','m3',0,96,900),
('2026-06-27','明光路制冷班','electricity_use','耗电量','Kwh',0,4259,147978),
('2026-06-27','明光路制冷班','gas_use','耗气量','m3',0,3137,182981),
('2026-06-27','苏里格制冷班','water_use','耗水量','m3',0,58,892),
('2026-06-27','苏里格制冷班','electricity_use','耗电量','Kwh',0,2035,83029),
('2026-06-27','苏里格制冷班','gas_use','耗气量','m3',0,1663,144548);

INSERT INTO maintenance_record
(report_date, category, location_name, daily_count, month_total, year_total, description) VALUES
('2026-06-27','水维修（公建）','兴隆园小区',4,135,872,'公建水维修参考记录'),
('2026-06-27','电维修（公建）','兴隆园小区',1,33,234,'公建电维修参考记录'),
('2026-06-27','维修服务','兴隆园小区',5,168,1098,'综合维修服务参考记录');

INSERT INTO equipment_runtime
(report_date, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, month_runtime_hours, year_runtime_hours) VALUES
('2026-06-27','锅炉运行班','1#锅炉',0,0,0,0,114.24,537.38),
('2026-06-27','锅炉运行班','2#锅炉',0,0,0,0,1.50,104.01),
('2026-06-27','锅炉运行班','3#锅炉',0.31,70,60,4.40,11.37,139.77),
('2026-06-27','锅炉运行班','4#锅炉',0,0,0,0,0,0),
('2026-06-27','科研楼制冷班','1#机组',NULL,0,0,0,0,1695),
('2026-06-27','科研楼制冷班','2#机组',NULL,0,0,0,0,1454),
('2026-06-27','科研楼制冷班','3#机组',NULL,0,0,0,48,735),
('2026-06-27','大厦制冷班','1#机组',NULL,0,0,0,48,1973),
('2026-06-27','大厦制冷班','2#机组',NULL,0,0,0,0,1886),
('2026-06-27','明光路制冷班','1#机组',NULL,0,0,0,26,1760),
('2026-06-27','明光路制冷班','6#机组',NULL,0,0,0,48,2332),
('2026-06-27','明光路制冷班','8#机组',NULL,0,0,0,22,473),
('2026-06-27','苏里格制冷班','1#机组',NULL,0,0,0,25,1252),
('2026-06-27','苏里格制冷班','2#机组',NULL,0,0,0,0,305);

INSERT INTO temperature_record
(report_date, location_name, temperature_type, temperature_c) VALUES
('2026-06-27','一区、三区热水','供水温度',58),
('2026-06-27','一区、三区热水','回水温度',52),
('2026-06-27','二区热水','供水温度',58),
('2026-06-27','二区热水','回水温度',52),
('2026-06-27','新三区热水','供水温度',57),
('2026-06-27','新三区热水','回水温度',51),
('2026-06-27','五区热水','供水温度',57),
('2026-06-27','五区热水','回水温度',51),
('2026-06-27','分水','温度',71),
('2026-06-27','增压站二区','出水温度',0),
('2026-06-27','增压站三区','出水温度',0),
('2026-06-27','增压站五区','出水温度',0);

-- 快速验证
SELECT daily_value AS expected_87000
FROM report_metric
WHERE report_date='2026-06-27' AND location_name='兴隆园小区' AND metric_code='electricity_supply';

SELECT pressure_mpa AS expected_0_31
FROM equipment_runtime
WHERE report_date='2026-06-27' AND team_name='锅炉运行班' AND equipment_name='3#锅炉';
