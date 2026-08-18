import unittest

from models.db_config import QueryBinding, QueryType, parse_sql_to_binding


class QueryBuilderTest(unittest.TestCase):
    def test_aggregate_query_with_join_and_filters(self):
        binding = QueryBinding(
            enabled=True, query_type=QueryType.AGGREGATE,
            table_name="production p", field_name="p.output", aggregate_func="SUM",
            joins=[{"type": "LEFT JOIN", "table": "station s", "on": "p.station_id = s.id"}],
            filters=[
                {"connector": "where", "field": "p.record_date", "op": "=", "value": "{date}"},
                {"connector": "and", "field": "s.region", "op": "LIKE", "value": "东区"},
            ],
        )
        sql = binding.build_sql("2026-08-13")
        self.assertEqual(sql, "SELECT SUM(p.output) FROM production p "
                              "LEFT JOIN station s ON p.station_id = s.id "
                              "WHERE p.record_date = '2026-08-13' AND s.region LIKE '%东区%'")

    def test_single_value_query(self):
        binding = QueryBinding(
            enabled=True, query_type=QueryType.SINGLE,
            table_name="daily", field_name="output",
        )
        self.assertEqual(binding.build_sql(), "SELECT output FROM daily")

    def test_old_binding_remains_compatible(self):
        binding = QueryBinding.from_dict({"enabled": True, "query_type": "aggregate",
                                          "table_name": "daily", "field_name": "output",
                                          "aggregate_func": "SUM", "filters": []})
        self.assertEqual(binding.build_sql(), "SELECT SUM(output) FROM daily")

    def test_simple_sql_is_safe_to_sync(self):
        info = parse_sql_to_binding("SELECT SUM(output) FROM daily WHERE day = '2026-08-13'")
        self.assertTrue(info["safe"])
        self.assertEqual(info["aggregate"], "SUM")
        self.assertEqual(info["filters"][0]["field"], "day")

    def test_complex_sql_is_not_destructively_synced(self):
        join = parse_sql_to_binding("SELECT a.x FROM a JOIN b ON a.id=b.id WHERE b.y=1")
        subquery = parse_sql_to_binding("SELECT x FROM a WHERE id IN (SELECT id FROM b)")
        self.assertFalse(join["safe"])
        self.assertFalse(subquery["safe"])

    def test_round_trip(self):
        original = QueryBinding(
            enabled=True, query_type=QueryType.AGGREGATE, sync_modes=True,
            table_name="a", field_name="a.x", aggregate_func="MAX",
            joins=[{"type": "INNER JOIN", "table": "b", "on": "a.id=b.id"}],
            filters=[{"connector": "where", "field": "a.k", "op": ">", "value": "0"}],
        )
        restored = QueryBinding.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())


if __name__ == "__main__":
    unittest.main()
