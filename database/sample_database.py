"""基于 2026-06-27《生产运行日报》的本地 SQLite 示例数据库。

示例库用于演示：数据库连接、元数据刷新、字段下拉、单元格查询绑定和报表预览。
不提交二进制数据库文件；需要时在用户数据目录动态生成。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


REPORT_DATE = "2026-06-27"


METRIC_ROWS = [
    # 区域/楼宇，指标编码，指标名称，单位，日值，月累计，年累计
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


MAINTENANCE_ROWS = [
    ("水维修（公建）", "兴隆园小区", 4, 135, 872, "公建水维修参考记录"),
    ("电维修（公建）", "兴隆园小区", 1, 33, 234, "公建电维修参考记录"),
    ("维修服务", "兴隆园小区", 5, 168, 1098, "综合维修服务参考记录"),
]


EQUIPMENT_ROWS = [
    # 班组，设备，压力，出水温度，回水温度，今日运行，月累，年累
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


TEMPERATURE_ROWS = [
    ("一区、三区热水", "供水温度", 58), ("一区、三区热水", "回水温度", 52),
    ("二区热水", "供水温度", 58), ("二区热水", "回水温度", 52),
    ("新三区热水", "供水温度", 57), ("新三区热水", "回水温度", 51),
    ("五区热水", "供水温度", 57), ("五区热水", "回水温度", 51),
    ("分水", "温度", 71),
    ("增压站二区", "出水温度", 0), ("增压站三区", "出水温度", 0),
    ("增压站五区", "出水温度", 0),
]


def default_sample_path() -> str:
    root = Path(os.path.expanduser("~")) / ".report_editor"
    root.mkdir(parents=True, exist_ok=True)
    return str(root / "sample_production_report.db")


def create_sample_database(path: str | None = None, reset: bool = True) -> str:
    """创建或重置示例数据库，并返回数据库文件路径。"""
    path = path or default_sample_path()
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset and db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS report_metric (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                location_name TEXT NOT NULL,
                metric_code TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                unit TEXT,
                daily_value REAL,
                month_total REAL,
                year_total REAL,
                UNIQUE(report_date, location_name, metric_code)
            );

            CREATE TABLE IF NOT EXISTS maintenance_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                category TEXT NOT NULL,
                location_name TEXT NOT NULL,
                daily_count INTEGER,
                month_total INTEGER,
                year_total INTEGER,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS equipment_runtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                team_name TEXT NOT NULL,
                equipment_name TEXT NOT NULL,
                pressure_mpa REAL,
                supply_temp_c REAL,
                return_temp_c REAL,
                runtime_hours REAL,
                month_runtime_hours REAL,
                year_runtime_hours REAL
            );

            CREATE TABLE IF NOT EXISTS temperature_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                location_name TEXT NOT NULL,
                temperature_type TEXT NOT NULL,
                temperature_c REAL
            );
            """
        )
        conn.execute("DELETE FROM report_metric WHERE report_date = ?", (REPORT_DATE,))
        conn.execute("DELETE FROM maintenance_record WHERE report_date = ?", (REPORT_DATE,))
        conn.execute("DELETE FROM equipment_runtime WHERE report_date = ?", (REPORT_DATE,))
        conn.execute("DELETE FROM temperature_record WHERE report_date = ?", (REPORT_DATE,))

        conn.executemany(
            "INSERT INTO report_metric(report_date, location_name, metric_code, metric_name, unit, daily_value, month_total, year_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(REPORT_DATE, *row) for row in METRIC_ROWS],
        )
        conn.executemany(
            "INSERT INTO maintenance_record(report_date, category, location_name, daily_count, month_total, year_total, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(REPORT_DATE, *row) for row in MAINTENANCE_ROWS],
        )
        conn.executemany(
            "INSERT INTO equipment_runtime(report_date, team_name, equipment_name, pressure_mpa, supply_temp_c, return_temp_c, runtime_hours, month_runtime_hours, year_runtime_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(REPORT_DATE, *row) for row in EQUIPMENT_ROWS],
        )
        conn.executemany(
            "INSERT INTO temperature_record(report_date, location_name, temperature_type, temperature_c) VALUES (?, ?, ?, ?)",
            [(REPORT_DATE, *row) for row in TEMPERATURE_ROWS],
        )
        conn.commit()
    finally:
        conn.close()
    return str(db_path)
