-- 维修服务参考数据库（MySQL 8+）
-- 2026-06-27 汇总值来自日报；工单明细为功能验证用演示数据。

CREATE DATABASE IF NOT EXISTS production_maintenance_demo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE production_maintenance_demo;

DROP TABLE IF EXISTS maintenance_order;
DROP TABLE IF EXISTS maintenance_daily;

CREATE TABLE maintenance_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  report_date DATE NOT NULL,
  category VARCHAR(100) NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  daily_count INT,
  month_total INT,
  year_total INT,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_maintenance_daily(report_date, category, location_name),
  KEY idx_maintenance_date(report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE maintenance_order (
  order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no VARCHAR(40) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL,
  completed_at DATETIME,
  category VARCHAR(100) NOT NULL,
  location_name VARCHAR(100) NOT NULL,
  requester VARCHAR(100),
  fault_description VARCHAR(255),
  handler_name VARCHAR(100),
  status VARCHAR(20) NOT NULL DEFAULT '已完成',
  duration_minutes INT,
  KEY idx_created_at(created_at),
  KEY idx_order_category(category),
  KEY idx_order_status(status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 日报参考汇总数据
INSERT INTO maintenance_daily(report_date, category, location_name, daily_count, month_total, year_total, updated_at) VALUES
('2026-06-27','水维修（公建）','兴隆园小区',4,135,872,'2026-06-27 18:00:00'),
('2026-06-27','电维修（公建）','兴隆园小区',1,33,234,'2026-06-27 18:00:00'),
('2026-06-27','维修服务','兴隆园小区',5,168,1098,'2026-06-27 18:00:00');

-- 下面为演示工单，用于筛选、LIKE、日期字段、状态统计等功能验证
INSERT INTO maintenance_order(order_no, created_at, completed_at, category, location_name, requester, fault_description, handler_name, status, duration_minutes) VALUES
('WX20260627001','2026-06-27 08:12:00','2026-06-27 09:05:00','水维修（公建）','兴隆园小区','物业前台','卫生间水龙头漏水','张师傅','已完成',53),
('WX20260627002','2026-06-27 09:20:00','2026-06-27 10:15:00','水维修（公建）','兴隆园小区','物业前台','公共区域阀门渗水','李师傅','已完成',55),
('WX20260627003','2026-06-27 10:30:00','2026-06-27 11:20:00','水维修（公建）','兴隆园小区','办公楼A座','洗手池下水不畅','张师傅','已完成',50),
('WX20260627004','2026-06-27 14:10:00','2026-06-27 15:00:00','水维修（公建）','兴隆园小区','办公楼B座','给水软管老化','李师傅','已完成',50),
('WX20260627005','2026-06-27 10:05:00','2026-06-27 10:42:00','电维修（公建）','兴隆园小区','物业前台','走廊照明故障','王师傅','已完成',37),
('WX20260627006','2026-06-27 08:45:00','2026-06-27 09:25:00','维修服务','兴隆园小区','会议中心','门锁故障','赵师傅','已完成',40),
('WX20260627007','2026-06-27 11:15:00','2026-06-27 12:05:00','维修服务','兴隆园小区','办公楼A座','窗户五金松动','赵师傅','已完成',50),
('WX20260627008','2026-06-27 13:20:00','2026-06-27 13:55:00','维修服务','兴隆园小区','物业前台','公共座椅松动','孙师傅','已完成',35),
('WX20260627009','2026-06-27 15:10:00','2026-06-27 15:50:00','维修服务','兴隆园小区','办公楼B座','吊顶检修口调整','孙师傅','已完成',40),
('WX20260627010','2026-06-27 16:05:00','2026-06-27 16:45:00','维修服务','兴隆园小区','会议中心','门吸损坏','赵师傅','已完成',40),
('WX20260626001','2026-06-26 09:00:00','2026-06-26 09:45:00','水维修（公建）','兴隆园小区','办公楼A座','阀门滴漏','张师傅','已完成',45),
('WX20260626002','2026-06-26 14:00:00','2026-06-26 14:30:00','维修服务','兴隆园小区','物业前台','门把手松动','赵师傅','已完成',30);

-- 验证示例：当天水维修工单数
SELECT COUNT(*) AS water_orders
FROM maintenance_order
WHERE category='水维修（公建）'
  AND created_at >= '2026-06-27 00:00:00'
  AND created_at < '2026-06-28 00:00:00';

-- 文本包含匹配示例
SELECT order_no, fault_description
FROM maintenance_order
WHERE fault_description LIKE '%漏%';
