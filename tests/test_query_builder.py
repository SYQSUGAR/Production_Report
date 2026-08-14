import unittest

from models.db_config import QueryBinding, QueryType, parse_sql_to_binding


class QueryBuilderTest(unittest.TestCase):
    def test_multi_table_aggregate_query(self):
        binding = QueryBinding(
            enabled=True, table_name="production p", distinct=True,
            select_fields=[
                {"field": "s.name", "aggregate": "", "alias": "station_name"},
                {"field": "p.output", "aggregate": "SUM", "alias": "total_output"},
            ],
            joins=[{"type": "LEFT JOIN", "table": "station s", "on": "p.station_id = s.id"}],
            filters=[
                {"connector": "where", "field": "p.record_date", "op": "=", "value": "{date}"},
                {"connector": "and", "field": "s.region", "op": "LIKE", "value": "东区"},
            ],
            group_by=["s.name"], having="SUM(p.output) > 100",
            order_by=[{"field": "total_output", "direction": "DESC"}], limit=10,
        )
        sql = binding.build_sql("2026-08-13")
        self.assertEqual(sql, "SELECT DISTINCT s.name AS station_name, SUM(p.output) AS total_output "
                              "FROM production p LEFT JOIN station s ON p.station_id = s.id "
                              "WHERE p.record_date = '2026-08-13' AND s.region LIKE '%东区%' "
                              "GROUP BY s.name HAVING SUM(p.output) > 100 "
                              "ORDER BY total_output DESC LIMIT 10")

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

    def test_round_trip_new_fields(self):
        original = QueryBinding(enabled=True, sync_modes=True, distinct=True,
                                joins=[{"type": "INNER JOIN", "table": "b", "on": "a.id=b.id"}],
                                select_fields=[{"field": "a.x", "aggregate": "MAX", "alias": "m"}],
                                group_by=["a.k"], having="MAX(a.x)>0",
                                order_by=[{"field": "m", "direction": "DESC"}], limit=5)
        restored = QueryBinding.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())


if __name__ == "__main__":
    unittest.main()
