-- 设备运行参考数据库（MySQL 8+）
-- 2026-06-27 核心数值来自日报；其余记录为时间筛选和聚合验证用演示数据。

CREATE DATABASE IF NOT EXISTS production_operation_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_operation_demo;

DROP TABLE IF EXISTS temperature_record;
DROP TABLE IF EXISTS equipment_runtime;

CREATE TABLE equipment_runtime (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  record_time DATETIME NOT NULL,
  report_date DATE NOT NULL,
  team_name VARCHAR(100) NOT NULL,
  equipment_name VARCHAR(100) NOT NULL,
  pressure_mpa DECIMAL(10,3),
  supply_temp_c DECIMAL(10,2),
  return_temp_c DECIMAL(10,2),
  runtime_hours DECIMAL(12,2),
  month_runtime_hours DECIMAL(12,2),
  year_runtime_hours DECIMAL(12,2),
  running_status VARCHAR(20) NOT NULL DEFAULT '停机',
  KEY idx_record_time(record_time),
  KEY idx_report_date(report_date),
  KEY idx_team_equipment(team_name, equipment_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE temperature_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  record_time DATETIME NOT NULL,
  report_date DATE NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  temperature_type VARCHAR(100) NOT NULL,
  temperature_c DECIMAL(10,2),
  KEY idx_temp_time(record_time),
  KEY idx_temp_location(location_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 演示数据：用于跨日/时间范围测试
INSERT INTO equipment_runtime(record_time, report_date, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, month_runtime_hours, year_runtime_hours, running_status) VALUES
('2026-06-25 08:00:00','2026-06-25','锅炉运行班','3#锅炉',0.30,69,59,4.2,2.77,131.17,'运行'),
('2026-06-26 08:00:00','2026-06-26','锅炉运行班','3#锅炉',0.31,70,60,4.2,6.97,135.37,'运行');

-- 2026-06-27 日报参考数据
INSERT INTO equipment_runtime(record_time, report_date, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, month_runtime_hours, year_runtime_hours, running_status) VALUES
('2026-06-27 08:00:00','2026-06-27','锅炉运行班','1#锅炉',0,0,0,0,114.24,537.38,'停机'),
('2026-06-27 08:00:00','2026-06-27','锅炉运行班','2#锅炉',0,0,0,0,1.50,104.01,'停机'),
('2026-06-27 08:00:00','2026-06-27','锅炉运行班','3#锅炉',0.31,70,60,4.40,11.37,139.77,'运行'),
('2026-06-27 08:00:00','2026-06-27','锅炉运行班','4#锅炉',0,0,0,0,0,0,'停机'),
('2026-06-27 08:00:00','2026-06-27','科研楼制冷班','1#机组',NULL,0,0,0,0,1695,'停机'),
('2026-06-27 08:00:00','2026-06-27','科研楼制冷班','2#机组',NULL,0,0,0,0,1454,'停机'),
('2026-06-27 08:00:00','2026-06-27','科研楼制冷班','3#机组',NULL,0,0,0,48,735,'停机'),
('2026-06-27 08:00:00','2026-06-27','大厦制冷班','1#机组',NULL,0,0,0,48,1973,'停机'),
('2026-06-27 08:00:00','2026-06-27','大厦制冷班','2#机组',NULL,0,0,0,0,1886,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','1#机组',NULL,0,0,0,26,1760,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','2#机组',NULL,0,0,0,26,1760,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','3#机组',NULL,0,0,0,26,1760,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','4#机组',NULL,0,0,0,26,1593,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','5#机组',NULL,0,0,0,0,971,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','6#机组',NULL,0,0,0,48,2332,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','7#机组',NULL,0,0,0,48,2044,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','8#机组',NULL,0,0,0,22,473,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','9#机组',NULL,0,0,0,0,909,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','10#机组',NULL,0,0,0,26,940,'停机'),
('2026-06-27 08:00:00','2026-06-27','明光路制冷班','11#机组',NULL,0,0,0,0,818,'停机'),
('2026-06-27 08:00:00','2026-06-27','苏里格制冷班','1#机组',NULL,0,0,0,25,1252,'停机'),
('2026-06-27 08:00:00','2026-06-27','苏里格制冷班','2#机组',NULL,0,0,0,0,305,'停机');

INSERT INTO temperature_record(record_time, report_date, location_name, temperature_type, temperature_c) VALUES
('2026-06-27 08:00:00','2026-06-27','一区、三区热水','供水温度',58),
('2026-06-27 08:00:00','2026-06-27','一区、三区热水','回水温度',52),
('2026-06-27 08:00:00','2026-06-27','二区热水','供水温度',58),
('2026-06-27 08:00:00','2026-06-27','二区热水','回水温度',52),
('2026-06-27 08:00:00','2026-06-27','新三区热水','供水温度',57),
('2026-06-27 08:00:00','2026-06-27','新三区热水','回水温度',51),
('2026-06-27 08:00:00','2026-06-27','五区热水','供水温度',57),
('2026-06-27 08:00:00','2026-06-27','五区热水','回水温度',51),
('2026-06-27 08:00:00','2026-06-27','分水','温度',71),
('2026-06-27 08:00:00','2026-06-27','增压站二区','出水温度',0),
('2026-06-27 08:00:00','2026-06-27','增压站三区','出水温度',0),
('2026-06-27 08:00:00','2026-06-27','增压站五区','出水温度',0);

-- 时间绑定验证示例
SELECT pressure_mpa
FROM equipment_runtime
WHERE equipment_name='3#锅炉'
  AND record_time >= '2026-06-27 00:00:00'
  AND record_time < '2026-06-28 00:00:00';
