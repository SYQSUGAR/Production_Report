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
