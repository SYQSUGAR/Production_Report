from models.db_config import QueryBinding, QueryType


def _binding():
    return QueryBinding(
        enabled=True,
        query_type=QueryType.SINGLE,
        database_name="production",
        qualify_database=True,
        table_name="equipment_status",
        source_alias="t1",
        source_mode="join",
        field_name="t2.equipment_name",
        joins=[
            {
                "type": "LEFT JOIN",
                "database_name": "production",
                "table_name": "equipment_info",
                "alias": "t2",
                "conditions": [
                    {"connector": "AND", "left": "t1.equipment_id", "op": "=", "right": "t2.equipment_id"},
                ],
            },
            {
                "type": "LEFT JOIN",
                "database_name": "production",
                "table_name": "location",
                "alias": "t3",
                "conditions": [
                    {"connector": "AND", "left": "t2.location_id", "op": "=", "right": "t3.location_id"},
                    {"connector": "AND", "left": "t2.enabled", "op": "=", "right": "t3.enabled"},
                ],
            },
        ],
        filters=[
            {"connector": "where", "field": "t2.equipment_type", "op": "=", "value": "锅炉"},
        ],
    )


def test_multi_join_sql_keeps_order_and_conditions():
    sql = _binding().build_sql()
    assert "FROM production.equipment_status t1" in sql
    first = sql.index("LEFT JOIN production.equipment_info t2")
    second = sql.index("LEFT JOIN production.location t3")
    assert first < second
    assert "t1.equipment_id = t2.equipment_id" in sql
    assert "t2.location_id = t3.location_id AND t2.enabled = t3.enabled" in sql
    assert "WHERE t2.equipment_type = '锅炉'" in sql


def test_merged_preview_only_contains_from_and_joins():
    sql = _binding().build_join_preview_sql(limit=20, db_type="mysql")
    assert sql.startswith("SELECT t1.*, t2.*, t3.*")
    assert "LEFT JOIN production.equipment_info t2" in sql
    assert "LEFT JOIN production.location t3" in sql
    assert "WHERE" not in sql
    assert "锅炉" not in sql
    assert sql.endswith("LIMIT 20")


def test_join_validation_rejects_missing_on_condition():
    qb = _binding()
    qb.joins[0]["conditions"] = []
    assert "尚未设置关联条件" in qb.validate_joins()


def test_source_mode_round_trip_and_legacy_inference():
    qb = _binding()
    restored = QueryBinding.from_dict(qb.to_dict())
    assert restored.source_mode == "join"

    legacy = qb.to_dict()
    legacy.pop("source_mode")
    assert QueryBinding.from_dict(legacy).source_mode == "join"

    single = QueryBinding.from_dict({"table_name": "equipment_status", "joins": []})
    assert single.source_mode == "single"


def test_join_on_skips_incomplete_condition_without_leading_connector():
    qb = _binding()
    qb.joins[0]["conditions"] = [
        {"connector": "AND", "left": "", "op": "=", "right": "t2.missing"},
        {"connector": "OR", "left": "t1.equipment_id", "op": "=", "right": "t2.equipment_id"},
    ]
    sql = qb.build_sql()
    assert " ON t1.equipment_id = t2.equipment_id" in sql
    assert " ON OR " not in sql


def test_single_mode_ignores_stale_join_configuration_and_validation():
    qb = _binding()
    qb.source_mode = "single"
    qb.field_name = "t1.equipment_id"
    qb.joins[0]["conditions"] = []  # 历史 JOIN 即使不完整也必须完全休眠。

    assert qb.validate_joins() == ""
    sql = qb.build_sql()
    assert " JOIN " not in sql
    assert " t1" not in sql
    assert "SELECT equipment_id FROM production.equipment_status" in sql


def test_single_mode_strips_stale_join_aliases_from_field_filter_and_time_field():
    qb = _binding()
    qb.source_mode = "single"
    qb.field_name = "t2.equipment_name"
    qb.filters = [
        {"connector": "where", "field": "t2.equipment_type", "op": "=", "value": "锅炉"},
    ]
    qb.time_binding.enabled = True
    qb.time_binding.time_field = "t3.record_time"

    sql = qb.build_sql(time_range=("2026-08-31 00:00:00", "2026-09-01 00:00:00"))
    assert " JOIN " not in sql
    assert "t1." not in sql
    assert "t2." not in sql
    assert "t3." not in sql
    assert "SELECT equipment_name FROM production.equipment_status" in sql
    assert "WHERE equipment_type = '锅炉'" in sql
    assert "record_time >=" in sql


def test_single_mode_join_preview_is_plain_single_table_preview():
    qb = _binding()
    qb.source_mode = "single"
    qb.joins[0]["conditions"] = []

    sql = qb.build_join_preview_sql(limit=20, db_type="mysql")
    assert sql == "SELECT * FROM production.equipment_status LIMIT 20"
