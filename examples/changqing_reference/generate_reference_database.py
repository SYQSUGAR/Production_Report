"""长庆油田生产运行日报参考数据库生成器。

这是独立案例工具，不被主程序导入。
根据 2026-06-27 日报最终结果反推一套“小时级原始参考数据”，用于演示：
- 日值 = 小时值 SUM
- 月累 = 当月小时值 SUM
- 年累 = 当年小时值 SUM
- 维修数量 = 事件 COUNT
- 运行时间 = 每小时运行小时数 SUM
- 温度/压力 = 小时采样 AVG

注意：Excel 只提供最终汇总结果，因此 2026-01-01～2026-06-27 的小时明细
是为了让汇总结果与日报一致而构造的演示数据，不代表真实历史采集值。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

REPORT_DAY = datetime(2026, 6, 27)
YEAR_START = datetime(2026, 1, 1)
MONTH_START = datetime(2026, 6, 1)
NEXT_DAY = datetime(2026, 6, 28)

UTILITY_TARGETS = [
    ("兴隆园小区", "water_supply", "供水量", "m3", 0, 18660, 126910),
    ("兴隆园小区", "electricity_supply", "供电量", "Kwh", 87000, 2429000, 16235774),
    ("兴隆园小区", "industrial_gas", "工业耗气量", "m3", 1590, 59219, 1191208),
    ("长庆综合科研楼", "water_use", "耗水量", "m3", 0, 0, 0),
    ("长庆综合科研楼", "electricity_use", "耗电量", "Kwh", 17385, 528000, 3342335),
    ("长庆大厦", "water_use", "耗水量", "m3", 9, 941, 4253),
    ("长庆大厦", "electricity_use", "耗电量", "Kwh", 12960, 370620, 1699925),
    ("苏里格大厦", "water_use", "耗水量", "m3", 32, 3345, 14290),
    ("苏里格大厦", "electricity_use", "耗电量", "Kwh", 10960, 368640, 2194220),
    ("长庆科技大厦", "water_use", "耗水量", "m3", 27, 577, 3967),
    ("长庆科技大厦", "electricity_use", "耗电量", "Kwh", 5440, 286120, 1844800),
    ("明光路办公区", "water_use", "耗水量", "m3", 103, 3592, 16665),
    ("明光路办公区", "electricity_use", "耗电量", "Kwh", 6210, 248850, 1283470),
    ("长实大厦", "electricity_supply", "供电量", "Kwh", 6300, 162700, 1033980),
    ("换热站", "electricity_use", "换热站耗电量", "Kwh", 240, 6960, 62680),
    ("锅炉房", "electricity_use", "锅炉房耗电量", "Kwh", 593.6, 15358.4, 162019.7),
    ("锅炉房", "gas_use", "耗气量", "Nm3", 1590, 48678, 300186),
    ("锅炉房", "hot_water_use", "卫生热水耗量", "m3", 523, 12970, 89289),
    ("锅炉房", "makeup_water", "补水量", "m3", 0.2, 5.4, 35.2),
    ("增压站二区", "electricity_use", "二区耗电量", "Kwh", 0, 0, 0),
    ("增压站三区", "electricity_use", "三区耗电量", "Kwh", 1480, 43123, 358097),
    ("增压站五区", "electricity_use", "五区耗电量", "Kwh", 0, 0, 0),
    ("科研楼制冷班", "water_use", "耗水量", "m3", 0, 118, 1446),
    ("科研楼制冷班", "electricity_use", "耗电量", "Kwh", 0, 5603, 180572),
    ("科研楼制冷班", "gas_use", "耗气量", "m3", 0, 2694, 276246),
    ("大厦制冷班", "water_use", "耗水量", "m3", 0, 90, 1580),
    ("大厦制冷班", "electricity_use", "耗电量", "Kwh", 0, 6614, 254243),
    ("大厦制冷班", "gas_use", "耗气量", "m3", 0, 3047, 287247),
    ("明光路制冷班", "water_use", "耗水量", "m3", 0, 96, 900),
    ("明光路制冷班", "electricity_use", "耗电量", "Kwh", 0, 4259, 147978),
    ("明光路制冷班", "gas_use", "耗气量", "m3", 0, 3137, 182981),
    ("苏里格制冷班", "water_use", "耗水量", "m3", 0, 58, 892),
    ("苏里格制冷班", "electricity_use", "耗电量", "Kwh", 0, 2035, 83029),
    ("苏里格制冷班", "gas_use", "耗气量", "m3", 0, 1663, 144548),
]

MAINTENANCE_TARGETS = [
    ("水维修（公建）", "兴隆园小区", 4, 135, 872),
    ("电维修（公建）", "兴隆园小区", 1, 33, 234),
    ("维修服务", "兴隆园小区", 5, 168, 1098),
]

EQUIPMENT_TARGETS = [
    ("锅炉运行班", "1#锅炉", 0, 0, 0, 0, 114.24, 537.38),
    ("锅炉运行班", "2#锅炉", 0, 0, 0, 0, 1.5, 104.01),
    ("锅炉运行班", "3#锅炉", 0.31, 70, 60, 4.4, 11.37, 139.77),
    ("锅炉运行班", "4#锅炉", 0, 0, 0, 0, 0, 0),
    ("科研楼制冷班", "1#机组", None, 0, 0, 0, 0, 1695),
    ("科研楼制冷班", "2#机组", None, 0, 0, 0, 0, 1454),
    ("科研楼制冷班", "3#机组", None, 0, 0, 0, 48, 735),
    ("大厦制冷班", "1#机组", None, 0, 0, 0, 48, 1973),
    ("大厦制冷班", "2#机组", None, 0, 0, 0, 0, 1886),
    ("明光路制冷班", "1#机组", None, 0, 0, 0, 26, 1760),
    ("明光路制冷班", "2#机组", None, 0, 0, 0, 26, 1760),
    ("明光路制冷班", "3#机组", None, 0, 0, 0, 26, 1760),
    ("明光路制冷班", "4#机组", None, 0, 0, 0, 26, 1593),
    ("明光路制冷班", "5#机组", None, 0, 0, 0, 0, 971),
    ("明光路制冷班", "6#机组", None, 0, 0, 0, 48, 2332),
    ("明光路制冷班", "7#机组", None, 0, 0, 0, 48, 2044),
    ("明光路制冷班", "8#机组", None, 0, 0, 0, 22, 473),
    ("明光路制冷班", "9#机组", None, 0, 0, 0, 0, 909),
    ("明光路制冷班", "10#机组", None, 0, 0, 0, 26, 940),
    ("明光路制冷班", "11#机组", None, 0, 0, 0, 0, 818),
    ("苏里格制冷班", "1#机组", None, 0, 0, 0, 25, 1252),
    ("苏里格制冷班", "2#机组", None, 0, 0, 0, 0, 305),
]

TEMPERATURE_TARGETS = [
    ("一区、三区热水", "出水温度", 58), ("一区、三区热水", "回水温度", 52),
    ("二区热水", "出水温度", 58), ("二区热水", "回水温度", 52),
    ("新三区热水", "出水温度", 57), ("新三区热水", "回水温度", 51),
    ("五区热水", "出水温度", 57), ("五区热水", "回水温度", 51),
    ("分水", "温度", 71),
    ("增压站二区", "出水温度", 0), ("增压站三区", "出水温度", 0),
    ("增压站五区", "出水温度", 0),
]


def hourly_timestamps(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        yield cursor
        cursor += timedelta(hours=1)


def _hour_weight(ts: datetime, salt: int) -> float:
    base = 1.0 + ((ts.hour + salt) % 7) * 0.025
    if 7 <= ts.hour < 22:
        base += 0.20
    if ts.weekday() >= 5:
        base *= 0.92
    return base


def distribute_total(total: float, start: datetime, end: datetime, salt: int):
    stamps = list(hourly_timestamps(start, end))
    if not stamps:
        return []
    total = float(total or 0)
    if total == 0:
        return [(ts, 0.0) for ts in stamps]
    weights = [_hour_weight(ts, salt) for ts in stamps]
    weight_sum = sum(weights)
    values = [round(total * w / weight_sum, 6) for w in weights]
    values[-1] = round(values[-1] + total - sum(values), 6)
    return list(zip(stamps, values))


def three_period_hourly(day_total: float, month_total: float, year_total: float, salt: int):
    day_total = float(day_total or 0)
    month_total = float(month_total or 0)
    year_total = float(year_total or 0)
    if day_total > month_total + 1e-8 or month_total > year_total + 1e-8:
        raise ValueError(f"汇总值不满足 日<=月<=年: {day_total}, {month_total}, {year_total}")
    rows = []
    rows += distribute_total(year_total - month_total, YEAR_START, MONTH_START, salt)
    rows += distribute_total(month_total - day_total, MONTH_START, REPORT_DAY, salt + 3)
    rows += distribute_total(day_total, REPORT_DAY, NEXT_DAY, salt + 6)
    return rows


def spread_events(count: int, start: datetime, end: datetime):
    count = int(count or 0)
    if count <= 0:
        return []
    seconds = max(1, int((end - start).total_seconds()))
    return [start + timedelta(seconds=((i + 1) * seconds) // (count + 1)) for i in range(count)]


def three_period_events(day_count: int, month_count: int, year_count: int):
    if day_count > month_count or month_count > year_count:
        raise ValueError("维修汇总值不满足 日<=月<=年")
    return (
        spread_events(year_count - month_count, YEAR_START, MONTH_START)
        + spread_events(month_count - day_count, MONTH_START, REPORT_DAY)
        + spread_events(day_count, REPORT_DAY, NEXT_DAY)
    )


MYSQL_DDL = [
    """
    CREATE TABLE IF NOT EXISTS cq_hourly_metric (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        record_time DATETIME NOT NULL,
        location_name VARCHAR(100) NOT NULL,
        metric_code VARCHAR(80) NOT NULL,
        metric_name VARCHAR(100) NOT NULL,
        unit VARCHAR(30),
        metric_value DECIMAL(18,6) NOT NULL,
        INDEX idx_cq_metric_time (record_time),
        INDEX idx_cq_metric_lookup (location_name, metric_code, record_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cq_equipment_hourly (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        record_time DATETIME NOT NULL,
        team_name VARCHAR(100) NOT NULL,
        equipment_name VARCHAR(100) NOT NULL,
        pressure_mpa DECIMAL(12,4) NULL,
        supply_temp_c DECIMAL(12,4) NULL,
        return_temp_c DECIMAL(12,4) NULL,
        runtime_hours DECIMAL(12,6) NOT NULL,
        INDEX idx_cq_equipment_time (record_time),
        INDEX idx_cq_equipment_lookup (team_name, equipment_name, record_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cq_temperature_hourly (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        record_time DATETIME NOT NULL,
        location_name VARCHAR(100) NOT NULL,
        temperature_type VARCHAR(60) NOT NULL,
        temperature_c DECIMAL(12,4) NOT NULL,
        INDEX idx_cq_temp_time (record_time),
        INDEX idx_cq_temp_lookup (location_name, temperature_type, record_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cq_maintenance_event (
        event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        event_time DATETIME NOT NULL,
        location_name VARCHAR(100) NOT NULL,
        category VARCHAR(100) NOT NULL,
        description VARCHAR(255),
        INDEX idx_cq_maintenance_time (event_time),
        INDEX idx_cq_maintenance_lookup (location_name, category, event_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]

SQLSERVER_DDL = [
    """
    IF OBJECT_ID(N'dbo.cq_hourly_metric', N'U') IS NULL
    CREATE TABLE dbo.cq_hourly_metric (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        record_time DATETIME2 NOT NULL,
        location_name NVARCHAR(100) NOT NULL,
        metric_code NVARCHAR(80) NOT NULL,
        metric_name NVARCHAR(100) NOT NULL,
        unit NVARCHAR(30) NULL,
        metric_value DECIMAL(18,6) NOT NULL
    )
    """,
    """
    IF OBJECT_ID(N'dbo.cq_equipment_hourly', N'U') IS NULL
    CREATE TABLE dbo.cq_equipment_hourly (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        record_time DATETIME2 NOT NULL,
        team_name NVARCHAR(100) NOT NULL,
        equipment_name NVARCHAR(100) NOT NULL,
        pressure_mpa DECIMAL(12,4) NULL,
        supply_temp_c DECIMAL(12,4) NULL,
        return_temp_c DECIMAL(12,4) NULL,
        runtime_hours DECIMAL(12,6) NOT NULL
    )
    """,
    """
    IF OBJECT_ID(N'dbo.cq_temperature_hourly', N'U') IS NULL
    CREATE TABLE dbo.cq_temperature_hourly (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        record_time DATETIME2 NOT NULL,
        location_name NVARCHAR(100) NOT NULL,
        temperature_type NVARCHAR(60) NOT NULL,
        temperature_c DECIMAL(12,4) NOT NULL
    )
    """,
    """
    IF OBJECT_ID(N'dbo.cq_maintenance_event', N'U') IS NULL
    CREATE TABLE dbo.cq_maintenance_event (
        event_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        event_time DATETIME2 NOT NULL,
        location_name NVARCHAR(100) NOT NULL,
        category NVARCHAR(100) NOT NULL,
        description NVARCHAR(255) NULL
    )
    """,
]


def connect(args):
    if args.db_type == "mysql":
        import pymysql
        return pymysql.connect(
            host=args.host, port=args.port or 3306, user=args.user,
            password=args.password, database=args.database, charset="utf8mb4",
        ), "%s", MYSQL_DDL
    import pyodbc
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={args.host},{args.port or 1433};DATABASE={args.database};"
        f"UID={args.user};PWD={args.password};"
    )
    return conn, "?", SQLSERVER_DDL


def delete_reference_range(cursor, p: str):
    for table, field in (
        ("cq_hourly_metric", "record_time"),
        ("cq_equipment_hourly", "record_time"),
        ("cq_temperature_hourly", "record_time"),
        ("cq_maintenance_event", "event_time"),
    ):
        cursor.execute(
            f"DELETE FROM {table} WHERE {field} >= {p} AND {field} < {p}",
            (YEAR_START, NEXT_DAY),
        )


def populate(args):
    conn, p, ddl = connect(args)
    cursor = conn.cursor()
    try:
        for statement in ddl:
            cursor.execute(statement)
        delete_reference_range(cursor, p)

        metric_sql = (
            "INSERT INTO cq_hourly_metric "
            "(record_time, location_name, metric_code, metric_name, unit, metric_value) "
            f"VALUES ({','.join([p] * 6)})"
        )
        for salt, (location, code, name, unit, day, month, year) in enumerate(UTILITY_TARGETS):
            rows = [
                (ts, location, code, name, unit, value)
                for ts, value in three_period_hourly(day, month, year, salt)
            ]
            cursor.executemany(metric_sql, rows)

        equipment_sql = (
            "INSERT INTO cq_equipment_hourly "
            "(record_time, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours) "
            f"VALUES ({','.join([p] * 7)})"
        )
        for salt, (team, equipment, pressure, supply, ret, day, month, year) in enumerate(EQUIPMENT_TARGETS):
            runtime = dict(three_period_hourly(day, month, year, salt + 100))
            rows = [
                (ts, team, equipment, pressure, supply, ret, runtime[ts])
                for ts in hourly_timestamps(YEAR_START, NEXT_DAY)
            ]
            cursor.executemany(equipment_sql, rows)

        temp_sql = (
            "INSERT INTO cq_temperature_hourly "
            "(record_time, location_name, temperature_type, temperature_c) "
            f"VALUES ({','.join([p] * 4)})"
        )
        for location, temp_type, value in TEMPERATURE_TARGETS:
            rows = [
                (ts, location, temp_type, value)
                for ts in hourly_timestamps(YEAR_START, NEXT_DAY)
            ]
            cursor.executemany(temp_sql, rows)

        maintenance_sql = (
            "INSERT INTO cq_maintenance_event "
            "(event_time, location_name, category, description) "
            f"VALUES ({','.join([p] * 4)})"
        )
        for category, location, day, month, year in MAINTENANCE_TARGETS:
            rows = [
                (ts, location, category, "参考案例事件")
                for ts in three_period_events(day, month, year)
            ]
            cursor.executemany(maintenance_sql, rows)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="生成长庆油田日报小时级参考数据库")
    parser.add_argument("--db-type", choices=["mysql", "sqlserver"], required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    populate(args)
    print("长庆油田小时级参考数据已写入数据库。")


if __name__ == "__main__":
    main()
