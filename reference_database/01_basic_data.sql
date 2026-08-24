-- 基础资料参考数据库（MySQL 8+）
-- 用途：验证基础数据类型、表名/字段下拉、关联查询。
-- 本脚本不修改程序源码。

CREATE DATABASE IF NOT EXISTS production_basic_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_basic_demo;

DROP TABLE IF EXISTS meter_point;
DROP TABLE IF EXISTS equipment;
DROP TABLE IF EXISTS team;
DROP TABLE IF EXISTS location;

CREATE TABLE location (
  location_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  location_code VARCHAR(32) NOT NULL UNIQUE,
  location_name VARCHAR(100) NOT NULL,
  location_type VARCHAR(32) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  remark VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE team (
  team_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  team_code VARCHAR(32) NOT NULL UNIQUE,
  team_name VARCHAR(100) NOT NULL,
  location_code VARCHAR(32),
  enabled TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE equipment (
  equipment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  equipment_code VARCHAR(32) NOT NULL UNIQUE,
  equipment_name VARCHAR(100) NOT NULL,
  equipment_type VARCHAR(32) NOT NULL,
  team_code VARCHAR(32),
  location_code VARCHAR(32),
  rated_power_kw DECIMAL(12,2),
  status VARCHAR(20) NOT NULL DEFAULT '在用',
  install_date DATE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE meter_point (
  meter_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  meter_code VARCHAR(32) NOT NULL UNIQUE,
  meter_name VARCHAR(100) NOT NULL,
  location_code VARCHAR(32) NOT NULL,
  medium_type VARCHAR(32) NOT NULL COMMENT 'water/electricity/gas/hot_water',
  unit VARCHAR(20) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO location(location_code, location_name, location_type, remark) VALUES
('XLXQ','兴隆园小区','园区','日报主园区'),
('KYL','长庆综合科研楼','办公楼',NULL),
('CQDS','长庆大厦','办公楼',NULL),
('SLGDS','苏里格大厦','办公楼',NULL),
('KJDS','长庆科技大厦','办公楼',NULL),
('MGL','明光路办公区','办公区',NULL),
('CSDS','长实大厦','办公楼',NULL),
('GLF','锅炉房','动力站房',NULL),
('HRZ','换热站','动力站房',NULL),
('ZYZ3','增压站三区','动力站房',NULL);

INSERT INTO team(team_code, team_name, location_code) VALUES
('GLYX','锅炉运行班','GLF'),
('KYLZL','科研楼制冷班','KYL'),
('DSZL','大厦制冷班','CQDS'),
('MGLZL','明光路制冷班','MGL'),
('SLGZL','苏里格制冷班','SLGDS'),
('WXFW','维修服务班','XLXQ');

INSERT INTO equipment(equipment_code, equipment_name, equipment_type, team_code, location_code, rated_power_kw, install_date) VALUES
('GL-01','1#锅炉','锅炉','GLYX','GLF',2800,'2019-10-01'),
('GL-02','2#锅炉','锅炉','GLYX','GLF',2800,'2019-10-01'),
('GL-03','3#锅炉','锅炉','GLYX','GLF',2800,'2019-10-01'),
('GL-04','4#锅炉','锅炉','GLYX','GLF',2800,'2019-10-01'),
('KYL-ZL-01','1#机组','制冷机组','KYLZL','KYL',850,'2020-05-01'),
('KYL-ZL-02','2#机组','制冷机组','KYLZL','KYL',850,'2020-05-01'),
('KYL-ZL-03','3#机组','制冷机组','KYLZL','KYL',850,'2020-05-01'),
('MGL-ZL-01','1#机组','制冷机组','MGLZL','MGL',900,'2021-04-15'),
('MGL-ZL-06','6#机组','制冷机组','MGLZL','MGL',900,'2021-04-15'),
('SLG-ZL-01','1#机组','制冷机组','SLGZL','SLGDS',800,'2020-06-01');

INSERT INTO meter_point(meter_code, meter_name, location_code, medium_type, unit) VALUES
('XL-W-01','兴隆园供水总表','XLXQ','water','m3'),
('XL-E-01','兴隆园供电总表','XLXQ','electricity','Kwh'),
('XL-G-01','兴隆园工业气总表','XLXQ','gas','m3'),
('KYL-E-01','科研楼电表','KYL','electricity','Kwh'),
('CQDS-E-01','长庆大厦电表','CQDS','electricity','Kwh'),
('GLF-G-01','锅炉房燃气表','GLF','gas','Nm3'),
('GLF-W-01','锅炉房卫生热水表','GLF','hot_water','m3');

-- 验证示例
SELECT * FROM location ORDER BY location_id;
SELECT equipment_name, equipment_type, team_code FROM equipment WHERE team_code='GLYX';
