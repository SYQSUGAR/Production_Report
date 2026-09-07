-- SQL Server 参考数据库（SQL Server 2019+）
-- 用途：验证程序原生 SQL Server 连接、表/字段刷新、查询和时间字段。
-- 数据结构与 MySQL 演示环境保持相近，但使用 SQL Server 语法。

IF DB_ID(N'production_sqlserver_demo') IS NULL
BEGIN
    CREATE DATABASE production_sqlserver_demo;
END;
GO

USE production_sqlserver_demo;
GO

IF OBJECT_ID(N'dbo.maintenance_order', N'U') IS NOT NULL DROP TABLE dbo.maintenance_order;
IF OBJECT_ID(N'dbo.equipment_runtime', N'U') IS NOT NULL DROP TABLE dbo.equipment_runtime;
IF OBJECT_ID(N'dbo.utility_daily', N'U') IS NOT NULL DROP TABLE dbo.utility_daily;
GO

CREATE TABLE dbo.utility_daily (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    report_date DATE NOT NULL,
    location_name NVARCHAR(100) NOT NULL,
    metric_code NVARCHAR(64) NOT NULL,
    metric_name NVARCHAR(100) NOT NULL,
    unit NVARCHAR(20) NULL,
    daily_value DECIMAL(18,3) NULL,
    month_total DECIMAL(18,3) NULL,
    year_total DECIMAL(18,3) NULL,
    updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE dbo.equipment_runtime (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    record_time DATETIME2 NOT NULL,
    team_name NVARCHAR(100) NOT NULL,
    equipment_name NVARCHAR(100) NOT NULL,
    pressure_mpa DECIMAL(10,3) NULL,
    supply_temp_c DECIMAL(10,2) NULL,
    return_temp_c DECIMAL(10,2) NULL,
    runtime_hours DECIMAL(12,2) NULL,
    running_status NVARCHAR(20) NOT NULL
);
GO

CREATE TABLE dbo.maintenance_order (
    order_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    order_no NVARCHAR(40) NOT NULL UNIQUE,
    created_at DATETIME2 NOT NULL,
    completed_at DATETIME2 NULL,
    category NVARCHAR(100) NOT NULL,
    location_name NVARCHAR(100) NOT NULL,
    fault_description NVARCHAR(255) NULL,
    handler_name NVARCHAR(100) NULL,
    status NVARCHAR(20) NOT NULL,
    duration_minutes INT NULL
);
GO

INSERT INTO dbo.utility_daily
(report_date, location_name, metric_code, metric_name, unit, daily_value, month_total, year_total, updated_at) VALUES
('2026-06-27',N'兴隆园小区',N'electricity_supply',N'供电量',N'Kwh',87000,2429000,16235774,'2026-06-27T23:30:00'),
('2026-06-27',N'兴隆园小区',N'industrial_gas',N'工业耗气量',N'm3',1590,59219,1191208,'2026-06-27T23:30:00'),
('2026-06-27',N'长庆综合科研楼',N'electricity_use',N'耗电量',N'Kwh',17385,528000,3342335,'2026-06-27T23:30:00'),
('2026-06-27',N'长庆大厦',N'electricity_use',N'耗电量',N'Kwh',12960,370620,1699925,'2026-06-27T23:30:00');
GO

INSERT INTO dbo.equipment_runtime
(record_time, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, running_status) VALUES
('2026-06-27T08:00:00',N'锅炉运行班',N'1#锅炉',0,0,0,0,N'停机'),
('2026-06-27T08:00:00',N'锅炉运行班',N'2#锅炉',0,0,0,0,N'停机'),
('2026-06-27T08:00:00',N'锅炉运行班',N'3#锅炉',0.31,70,60,4.40,N'运行');
GO

INSERT INTO dbo.maintenance_order
(order_no, created_at, completed_at, category, location_name, fault_description, handler_name, status, duration_minutes) VALUES
(N'WX20260627001','2026-06-27T08:12:00','2026-06-27T09:05:00',N'水维修（公建）',N'兴隆园小区',N'卫生间水龙头漏水',N'张师傅',N'已完成',53),
(N'WX20260627002','2026-06-27T09:20:00','2026-06-27T10:15:00',N'水维修（公建）',N'兴隆园小区',N'公共区域阀门渗水',N'李师傅',N'已完成',55),
(N'WX20260627005','2026-06-27T10:05:00','2026-06-27T10:42:00',N'电维修（公建）',N'兴隆园小区',N'走廊照明故障',N'王师傅',N'已完成',37);
GO

-- 验证查询
SELECT daily_value
FROM dbo.utility_daily
WHERE report_date='2026-06-27'
  AND location_name=N'兴隆园小区'
  AND metric_code=N'electricity_supply';
GO

SELECT pressure_mpa
FROM dbo.equipment_runtime
WHERE equipment_name=N'3#锅炉'
  AND record_time >= '2026-06-27T00:00:00'
  AND record_time < '2026-06-28T00:00:00';
GO
