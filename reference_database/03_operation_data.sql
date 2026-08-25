-- 设备运行参考数据库（MySQL 8+）
-- 设计原则：设备基本信息每台设备只保存一行；设备状态按 equipment_id + record_time 保存多条历史记录。
-- equipment_id 直接使用业务设备编号（如 GL-03），状态表不保存设备名称。
-- 2026-06-27 核心数值来自用户提供日报；2026-06-25～26 为时间筛选和 JOIN 验证用演示数据。

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS production_operation_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_operation_demo;

DROP TABLE IF EXISTS temperature_record;
DROP TABLE IF EXISTS equipment_status;
DROP TABLE IF EXISTS equipment_runtime;
DROP TABLE IF EXISTS equipment_info;

CREATE TABLE equipment_info (
  equipment_id VARCHAR(32) PRIMARY KEY COMMENT '业务设备编号，如 GL-03',
  equipment_name VARCHAR(100) NOT NULL,
  equipment_type VARCHAR(32) NOT NULL,
  team_name VARCHAR(100),
  location_name VARCHAR(100),
  manufacturer VARCHAR(100),
  model VARCHAR(100),
  rated_power_kw DECIMAL(12,2),
  install_date DATE,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  remark VARCHAR(255),
  KEY idx_equipment_type(equipment_type),
  KEY idx_equipment_team(team_name),
  KEY idx_equipment_location(location_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE equipment_status (
  status_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  equipment_id VARCHAR(32) NOT NULL COMMENT '关联 equipment_info.equipment_id',
  record_time DATETIME NOT NULL,
  report_date DATE NOT NULL,
  pressure_mpa DECIMAL(10,3),
  supply_temp_c DECIMAL(10,2),
  return_temp_c DECIMAL(10,2),
  runtime_hours DECIMAL(12,2),
  month_runtime_hours DECIMAL(12,2),
  year_runtime_hours DECIMAL(12,2),
  running_status VARCHAR(20) NOT NULL DEFAULT '停机',
  remark VARCHAR(255),
  CONSTRAINT fk_equipment_status_equipment
    FOREIGN KEY (equipment_id) REFERENCES equipment_info(equipment_id),
  UNIQUE KEY uk_equipment_time(equipment_id, record_time),
  KEY idx_status_record_time(record_time),
  KEY idx_status_report_date(report_date),
  KEY idx_status_equipment_date(equipment_id, report_date)
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

-- 设备基本信息：每台设备只保存一行，equipment_id 就是业务编号。
INSERT INTO equipment_info
(equipment_id, equipment_name, equipment_type, team_name, location_name, manufacturer, model, rated_power_kw, install_date, remark) VALUES
('GL-01','1#锅炉','锅炉','锅炉运行班','锅炉房','测试厂家A','GL-2800',2800,'2019-10-01','日报参考设备'),
('GL-02','2#锅炉','锅炉','锅炉运行班','锅炉房','测试厂家A','GL-2800',2800,'2019-10-01','日报参考设备'),
('GL-03','3#锅炉','锅炉','锅炉运行班','锅炉房','测试厂家A','GL-2800',2800,'2019-10-01','日报参考设备'),
('GL-04','4#锅炉','锅炉','锅炉运行班','锅炉房','测试厂家A','GL-2800',2800,'2019-10-01','日报参考设备'),
('KYL-ZL-01','1#机组','制冷机组','科研楼制冷班','长庆综合科研楼','测试厂家B','ZL-850',850,'2020-05-01','演示基础信息'),
('KYL-ZL-02','2#机组','制冷机组','科研楼制冷班','长庆综合科研楼','测试厂家B','ZL-850',850,'2020-05-01','演示基础信息'),
('KYL-ZL-03','3#机组','制冷机组','科研楼制冷班','长庆综合科研楼','测试厂家B','ZL-850',850,'2020-05-01','演示基础信息'),
('DS-ZL-01','1#机组','制冷机组','大厦制冷班','长庆大厦','测试厂家C','ZL-900',900,'2020-06-01','演示基础信息'),
('DS-ZL-02','2#机组','制冷机组','大厦制冷班','长庆大厦','测试厂家C','ZL-900',900,'2020-06-01','演示基础信息'),
('MGL-ZL-01','1#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-02','2#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-03','3#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-04','4#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-05','5#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-06','6#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-07','7#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-08','8#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-09','9#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-10','10#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('MGL-ZL-11','11#机组','制冷机组','明光路制冷班','明光路办公区','测试厂家D','ZL-900',900,'2021-04-15','演示基础信息'),
('SLG-ZL-01','1#机组','制冷机组','苏里格制冷班','苏里格大厦','测试厂家E','ZL-800',800,'2020-06-01','演示基础信息'),
('SLG-ZL-02','2#机组','制冷机组','苏里格制冷班','苏里格大厦','测试厂家E','ZL-800',800,'2020-06-01','演示基础信息');

-- 同一设备 GL-03 在不同日期有多条状态记录。
INSERT INTO equipment_status
(equipment_id, record_time, report_date, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, month_runtime_hours, year_runtime_hours, running_status) VALUES
('GL-03','2026-06-25 08:00:00','2026-06-25',0.30,69,59,4.20,2.77,131.17,'运行'),
('GL-03','2026-06-26 08:00:00','2026-06-26',0.31,70,60,4.20,6.97,135.37,'运行'),
('GL-01','2026-06-27 08:00:00','2026-06-27',0,0,0,0,114.24,537.38,'停机'),
('GL-02','2026-06-27 08:00:00','2026-06-27',0,0,0,0,1.50,104.01,'停机'),
('GL-03','2026-06-27 08:00:00','2026-06-27',0.31,70,60,4.40,11.37,139.77,'运行'),
('GL-04','2026-06-27 08:00:00','2026-06-27',0,0,0,0,0,0,'停机'),
('KYL-ZL-01','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,1695,'停机'),
('KYL-ZL-02','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,1454,'停机'),
('KYL-ZL-03','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,48,735,'停机'),
('DS-ZL-01','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,48,1973,'停机'),
('DS-ZL-02','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,1886,'停机'),
('MGL-ZL-01','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,26,1760,'停机'),
('MGL-ZL-02','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,26,1760,'停机'),
('MGL-ZL-03','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,26,1760,'停机'),
('MGL-ZL-04','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,26,1593,'停机'),
('MGL-ZL-05','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,971,'停机'),
('MGL-ZL-06','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,48,2332,'停机'),
('MGL-ZL-07','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,48,2044,'停机'),
('MGL-ZL-08','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,22,473,'停机'),
('MGL-ZL-09','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,909,'停机'),
('MGL-ZL-10','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,26,940,'停机'),
('MGL-ZL-11','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,818,'停机'),
('SLG-ZL-01','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,25,1252,'停机'),
('SLG-ZL-02','2026-06-27 08:00:00','2026-06-27',NULL,0,0,0,0,305,'停机');

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

-- JOIN 验证：设备名称只来自基本信息表，状态表只存设备编号和状态数据。
SELECT
  e.equipment_id,
  e.equipment_name,
  e.equipment_type,
  s.record_time,
  s.pressure_mpa,
  s.running_status
FROM equipment_info e
JOIN equipment_status s ON s.equipment_id = e.equipment_id
WHERE e.equipment_id='GL-03'
ORDER BY s.record_time;
