"""时间 SQL 模板与最终显示格式测试。"""

from datetime import datetime

from models.db_config import QueryBinding, QueryType
from models.time_binding import TimeBinding, TimeRangeType, TimeMode
from models.value_formatter import format_display_value, coerce_excel_value


def _builder_binding():
    return QueryBinding(
        enabled=True,
        query_type=QueryType.AGGREGATE,
        table_name="production",
        field_name="output_value",
        aggregate_func="SUM",
        time_binding=TimeBinding(
            enabled=True,
            time_field="record_time",
            range_type=TimeRangeType.DAY,
            mode=TimeMode.SELECTED,
        ),
    )


def test_builder_preview_uses_runtime_placeholders():
    sql = _builder_binding().build_sql()
    assert "record_time >= {start_time}" in sql
    assert "record_time < {end_time}" in sql


def test_builder_runtime_replaces_time_placeholders():
    binding = _builder_binding()
    sql = binding.build_sql(time_range=(
        datetime(2026, 8, 19, 0, 0, 0),
        datetime(2026, 8, 20, 0, 0, 0),
    ))
    assert "{start_time}" not in sql
    assert "{end_time}" not in sql
    assert "'2026-08-19 00:00:00'" in sql
    assert "'2026-08-20 00:00:00'" in sql


def test_manual_dynamic_time_requires_both_placeholders():
    binding = _builder_binding()
    binding.sql_mode = "manual"
    binding.custom_sql = "SELECT SUM(output_value) FROM production"
    assert "必须同时包含" in binding.validate_time_sql()

    binding.custom_sql = (
        "SELECT SUM(output_value) FROM production "
        "WHERE record_time >= {start_time} AND record_time < {end_time}"
    )
    assert binding.validate_time_sql() == ""


def test_display_value_formats_database_results():
    assert format_display_value("1234.567", "integer") == "1,235"
    assert format_display_value("1234.567", "decimal_2") == "1,234.57"
    assert format_display_value("0.126", "percent") == "12.60%"
    assert format_display_value("2026-08-19", "yyyy-mm-dd") == "2026-08-19"


def test_excel_value_is_coerced_by_number_format():
    assert coerce_excel_value("1234.567", "integer") == 1235
    assert coerce_excel_value("1234.567", "decimal_2") == 1234.567
    assert coerce_excel_value("0.126", "percent") == 0.126
