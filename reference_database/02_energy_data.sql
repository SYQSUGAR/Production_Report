-- 能源与消耗参考数据库（MySQL 8+）
-- 2026-06-27 核心数值来自用户提供日报；2026-06-25~26 为功能验证用演示数据。

CREATE DATABASE IF NOT EXISTS production_energy_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_energy_demo;

DROP TABLE IF EXISTS utility_daily;
DROP TABLE IF EXISTS utility_metric;

CREATE TABLE utility_metric (
  metric_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  metric_code VARCHAR(64) NOT NULL UNIQUE,
  metric_name VARCHAR(100) NOT NULL,
  medium_type VARCHAR(32) NOT NULL,
  unit VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE utility_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  metric_code VARCHAR(64) NOT NULL,
  daily_value DECIMAL(18,3),
  month_total DECIMAL(18,3),
  year_total DECIMAL(18,3),
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_daily (report_date, location_name, metric_code),
  KEY idx_report_date (report_date),
  KEY idx_location (location_name),
  KEY idx_metric (metric_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO utility_metric(metric_code, metric_name, medium_type, unit) VALUES
('water_supply','供水量','water','m3'),
('electricity_supply','供电量','electricity','Kwh'),
('industrial_gas','工业耗气量','gas','m3'),
('water_use','耗水量','water','m3'),
('electricity_use','耗电量','electricity','Kwh'),
('gas_use','耗气量','gas','m3'),
('hot_water_use','卫生热水耗量','hot_water','m3'),
('makeup_water','补水量','water','m3');

-- 2026-06-25~26 为演示数据，用于时间筛选/聚合验证
INSERT INTO utility_daily(report_date, location_name, metric_code, daily_value, month_total, year_total, updated_at) VALUES
('2026-06-25','兴隆园小区','electricity_supply',85200,2250000,16061774,'2026-06-25 23:30:00'),
('2026-06-26','兴隆园小区','electricity_supply',87400,2342000,16148774,'2026-06-26 23:30:00'),
('2026-06-25','兴隆园小区','industrial_gas',1620,56030,1188018,'2026-06-25 23:30:00'),
('2026-06-26','兴隆园小区','industrial_gas',1595,57629,1189613,'2026-06-26 23:30:00'),
('2026-06-25','长庆综合科研楼','electricity_use',16820,493100,3308130,'2026-06-25 23:30:00'),
('2026-06-26','长庆综合科研楼','electricity_use',17410,510615,3324950,'2026-06-26 23:30:00');

-- 2026-06-27：日报参考数据
INSERT INTO utility_daily(report_date, location_name, metric_code, daily_value, month_total, year_total, updated_at) VALUES
('2026-06-27','兴隆园小区','water_supply',0,18660,126910,'2026-06-27 23:30:00'),
('2026-06-27','兴隆园小区','electricity_supply',87000,2429000,16235774,'2026-06-27 23:30:00'),
('2026-06-27','兴隆园小区','industrial_gas',1590,59219,1191208,'2026-06-27 23:30:00'),
('2026-06-27','长庆综合科研楼','water_use',0,0,0,'2026-06-27 23:30:00'),
('2026-06-27','长庆综合科研楼','electricity_use',17385,528000,3342335,'2026-06-27 23:30:00'),
('2026-06-27','长庆大厦','water_use',9,941,4253,'2026-06-27 23:30:00'),
('2026-06-27','长庆大厦','electricity_use',12960,370620,1699925,'2026-06-27 23:30:00'),
('2026-06-27','苏里格大厦','water_use',32,3345,14290,'2026-06-27 23:30:00'),
('2026-06-27','苏里格大厦','electricity_use',10960,368640,2194220,'2026-06-27 23:30:00'),
('2026-06-27','长庆科技大厦','water_use',27,577,3967,'2026-06-27 23:30:00'),
('2026-06-27','长庆科技大厦','electricity_use',5440,286120,1844800,'2026-06-27 23:30:00'),
('2026-06-27','明光路办公区','water_use',103,3592,16665,'2026-06-27 23:30:00'),
('2026-06-27','明光路办公区','electricity_use',6210,248850,1283470,'2026-06-27 23:30:00'),
('2026-06-27','长实大厦','electricity_supply',6300,162700,1033980,'2026-06-27 23:30:00'),
('2026-06-27','换热站','electricity_use',240,6960,62680,'2026-06-27 23:30:00'),
('2026-06-27','锅炉房','electricity_use',593.6,15358.4,162019.7,'2026-06-27 23:30:00'),
('2026-06-27','锅炉房','gas_use',1590,48678,300186,'2026-06-27 23:30:00'),
('2026-06-27','锅炉房','hot_water_use',523,12970,89289,'2026-06-27 23:30:00'),
('2026-06-27','锅炉房','makeup_water',0.2,5.4,35.2,'2026-06-27 23:30:00'),
('2026-06-27','增压站三区','electricity_use',1480,43123,358097,'2026-06-27 23:30:00'),
('2026-06-27','科研楼制冷班','water_use',0,118,1446,'2026-06-27 23:30:00'),
('2026-06-27','科研楼制冷班','electricity_use',0,5603,180572,'2026-06-27 23:30:00'),
('2026-06-27','科研楼制冷班','gas_use',0,2694,276246,'2026-06-27 23:30:00'),
('2026-06-27','大厦制冷班','water_use',0,90,1580,'2026-06-27 23:30:00'),
('2026-06-27','大厦制冷班','electricity_use',0,6614,254243,'2026-06-27 23:30:00'),
('2026-06-27','大厦制冷班','gas_use',0,3047,287247,'2026-06-27 23:30:00'),
('2026-06-27','明光路制冷班','water_use',0,96,900,'2026-06-27 23:30:00'),
('2026-06-27','明光路制冷班','electricity_use',0,4259,147978,'2026-06-27 23:30:00'),
('2026-06-27','明光路制冷班','gas_use',0,3137,182981,'2026-06-27 23:30:00'),
('2026-06-27','苏里格制冷班','water_use',0,58,892,'2026-06-27 23:30:00'),
('2026-06-27','苏里格制冷班','electricity_use',0,2035,83029,'2026-06-27 23:30:00'),
('2026-06-27','苏里格制冷班','gas_use',0,1663,144548,'2026-06-27 23:30:00');

-- 关联查询示例：指标中文名 + 日值
SELECT d.report_date, d.location_name, m.metric_name, m.unit, d.daily_value
FROM utility_daily d
LEFT JOIN utility_metric m ON d.metric_code=m.metric_code
WHERE d.report_date='2026-06-27' AND d.location_name='兴隆园小区';

-- 聚合示例
SELECT SUM(daily_value) AS three_day_electricity
FROM utility_daily
WHERE location_name='兴隆园小区'
  AND metric_code='electricity_supply'
  AND report_date >= '2026-06-25' AND report_date < '2026-06-28';
