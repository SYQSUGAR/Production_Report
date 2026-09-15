"""报表时间绑定核心逻辑测试。"""

import unittest
from datetime import date, datetime

from models.db_config import QueryBinding, QueryType
from models.report_context import ReportContext
from models.time_binding import TimeBinding, TimeMode, TimeRangeType


class ReportTimeTests(unittest.TestCase):
    def setUp(self):
        self.ctx = ReportContext(
            generated_at=datetime(2026, 8, 19, 11, 30, 0),
            selected_day=date(2026, 8, 12),
            selected_month_year=2026,
            selected_month=7,
            selected_year=2025,
            custom_start=datetime(2026, 6, 1, 8, 0, 0),
            custom_end=datetime(2026, 6, 5, 18, 0, 0),
        )

    def test_current_day_is_cut_at_generated_time(self):
        binding = TimeBinding(True, "record_time", TimeRangeType.DAY, TimeMode.CURRENT)
        self.assertEqual(
            self.ctx.resolve(binding),
            (datetime(2026, 8, 19, 0, 0, 0), datetime(2026, 8, 19, 11, 30, 0)),
        )

    def test_selected_month_is_full_month(self):
        binding = TimeBinding(True, "record_time", TimeRangeType.MONTH, TimeMode.SELECTED)
        self.assertEqual(
            self.ctx.resolve(binding),
            (datetime(2026, 7, 1, 0, 0, 0), datetime(2026, 8, 1, 0, 0, 0)),
        )

    def test_builder_appends_half_open_time_range(self):
        binding = QueryBinding(
            enabled=True,
            query_type=QueryType.AGGREGATE,
            table_name="production",
            field_name="output",
            aggregate_func="SUM",
            filters=[{"connector": "where", "field": "workshop", "op": "=", "value": "一车间"}],
            time_binding=TimeBinding(True, "record_time", TimeRangeType.DAY, TimeMode.SELECTED),
        )
        sql = binding.build_sql(time_range=self.ctx.resolve(binding.time_binding))
        self.assertIn("SELECT SUM(output) FROM production", sql)
        self.assertIn("WHERE workshop = '一车间'", sql)
        self.assertIn("record_time >= '2026-08-12 00:00:00'", sql)
        self.assertIn("record_time < '2026-08-13 00:00:00'", sql)

    def test_manual_sql_replaces_time_placeholders(self):
        binding = QueryBinding(
            enabled=True,
            sql_mode="manual",
            custom_sql="SELECT SUM(output) FROM production WHERE record_time >= {start_time} AND record_time < {end_time}",
            time_binding=TimeBinding(True, "record_time", TimeRangeType.CUSTOM, TimeMode.SELECTED),
        )
        sql = binding.build_sql(time_range=self.ctx.resolve(binding.time_binding))
        self.assertIn("'2026-06-01 08:00:00'", sql)
        self.assertIn("'2026-06-05 18:00:00'", sql)


if __name__ == "__main__":
    unittest.main()
