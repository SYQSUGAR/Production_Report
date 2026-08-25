-- 设备运行参考数据库（MySQL 8+）
-- 设备属性与时序状态严格分离：
--   equipment_info   每台设备只保存一行基本属性；
--   equipment_status 只保存 equipment_id + record_time + temperature_c。
-- 状态数据按小时记录，连续 5 天（2026-06-23 00:00:00 ~ 2026-06-27 23:00:00），
-- 每台设备 120 条记录。温度为软件验证用演示数据，不代表真实生产记录。

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
  equipment_name VARCHAR(100) NOT NULL COMMENT '设备名称',
  equipment_type VARCHAR(50) COMMENT '设备类型',
  team_name VARCHAR(100) COMMENT '所属班组',
  location_name VARCHAR(100) COMMENT '安装位置',
  manufacturer VARCHAR(100) COMMENT '厂家',
  model VARCHAR(100) COMMENT '型号',
  rated_power_kw DECIMAL(12,2) COMMENT '额定功率(kW)',
  install_date DATE COMMENT '安装日期',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  remark VARCHAR(255) COMMENT '其他设备信息',
  KEY idx_equipment_name(equipment_name),
  KEY idx_equipment_type(equipment_type),
  KEY idx_equipment_location(location_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE equipment_status (
  equipment_id VARCHAR(32) NOT NULL COMMENT '关联 equipment_info.equipment_id',
  record_time DATETIME NOT NULL COMMENT '整点时间，每小时一条',
  temperature_c DECIMAL(6,2) NOT NULL COMMENT '设备温度(°C)',
  PRIMARY KEY (equipment_id, record_time),
  KEY idx_status_time(record_time),
  CONSTRAINT fk_equipment_status_equipment
    FOREIGN KEY (equipment_id) REFERENCES equipment_info(equipment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 设备基本信息：每台设备严格一行。
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

-- 生成 120 个连续整点：2026-06-23 00:00 到 2026-06-27 23:00。
-- 与所有设备做笛卡尔组合，因此每台设备都有完整 5 天、每小时一条的状态记录。
WITH RECURSIVE hours AS (
  SELECT 0 AS hour_offset
  UNION ALL
  SELECT hour_offset + 1 FROM hours WHERE hour_offset < 119
)
INSERT INTO equipment_status (equipment_id, record_time, temperature_c)
SELECT
  e.equipment_id,
  TIMESTAMP('2026-06-23 00:00:00') + INTERVAL h.hour_offset HOUR,
  ROUND(
    CASE
      WHEN e.equipment_type = '锅炉' THEN
        55 + MOD(CRC32(e.equipment_id), 6)
           + 5 * SIN(2 * PI() * MOD(h.hour_offset, 24) / 24)
           + MOD(h.hour_offset, 5) * 0.20
      ELSE
        22 + MOD(CRC32(e.equipment_id), 5)
           + 3 * SIN(2 * PI() * MOD(h.hour_offset, 24) / 24)
           + MOD(h.hour_offset, 4) * 0.15
    END,
    2
  ) AS temperature_c
FROM equipment_info e
CROSS JOIN hours h;

-- 验证：每台设备应恰好 120 条，每小时一条。
SELECT equipment_id, COUNT(*) AS hourly_rows,
       MIN(record_time) AS first_time,
       MAX(record_time) AS last_time
FROM equipment_status
GROUP BY equipment_id
ORDER BY equipment_id;

-- JOIN 验证：状态表没有设备名称，名称只能从 equipment_info 合并取得。
SELECT
  e.equipment_id,
  e.equipment_name,
  e.equipment_type,
  s.record_time,
  s.temperature_c
FROM equipment_info e
JOIN equipment_status s ON s.equipment_id = e.equipment_id
WHERE e.equipment_id = 'GL-03'
ORDER BY s.record_time
LIMIT 24;
