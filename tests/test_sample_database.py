import os
import tempfile
import unittest

from database.db_handler import DbHandler
from database.sample_database import create_sample_database
from models.db_config import DbConfig


class SampleDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "sample.db")
        create_sample_database(self.db_path, reset=True)
        self.handler = DbHandler()
        self.config = DbConfig(db_type="sqlite", database=self.db_path)

    def tearDown(self):
        self.handler.disconnect_all()
        self.temp_dir.cleanup()

    def test_schema_and_reference_values(self):
        self.assertTrue(self.handler.connect(self.config, "default"))
        metadata = self.handler.get_schema_metadata("default")

        self.assertEqual(
            set(metadata),
            {"report_metric", "maintenance_record", "equipment_runtime", "temperature_record"},
        )
        self.assertIn("report_date", metadata["report_metric"])
        self.assertIn("daily_value", metadata["report_metric"])
        self.assertIn("equipment_name", metadata["equipment_runtime"])

        electricity = self.handler.execute_query(
            "SELECT daily_value FROM report_metric "
            "WHERE report_date='2026-06-27' "
            "AND location_name='兴隆园小区' "
            "AND metric_code='electricity_supply'",
            "default",
        )
        self.assertEqual(electricity, "87000.0")

        pressure = self.handler.execute_query(
            "SELECT pressure_mpa FROM equipment_runtime "
            "WHERE report_date='2026-06-27' "
            "AND team_name='锅炉运行班' AND equipment_name='3#锅炉'",
            "default",
        )
        self.assertEqual(pressure, "0.31")

        maintenance = self.handler.execute_query(
            "SELECT daily_count FROM maintenance_record "
            "WHERE report_date='2026-06-27' AND category='水维修（公建）'",
            "default",
        )
        self.assertEqual(maintenance, "4")


if __name__ == "__main__":
    unittest.main()
