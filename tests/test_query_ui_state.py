import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from models.template_model import TemplateModel
from ui.style_panel import StylePanel


class QueryUiStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = StylePanel(TemplateModel(3, 3))
        self.panel.set_current_selection("cell", 0, 0)
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()

    def test_database_switch_locks_number_format_and_greys_query_controls(self):
        self.assertFalse(self.panel._cmb_sql_mode.isEnabled())
        self.assertTrue(self.panel._cmb_number_cat.isEnabled())
        self.assertTrue(self.panel._lbl_nf_db_lock.isHidden())

        self.panel._chk_db_enabled.setChecked(True)
        self.app.processEvents()

        self.assertTrue(self.panel._cmb_sql_mode.isEnabled())
        self.assertFalse(self.panel._cmb_number_cat.isEnabled())
        self.assertFalse(self.panel._lbl_nf_db_lock.isHidden())

    def test_query_type_only_shows_aggregate_controls_when_needed(self):
        self.panel._chk_db_enabled.setChecked(True)
        self.panel._cmb_query_type.setCurrentIndex(0)
        self.assertTrue(self.panel._agg_widget.isHidden())

        self.panel._cmb_query_type.setCurrentIndex(1)
        self.assertFalse(self.panel._agg_widget.isHidden())

    def test_optional_sections_require_their_own_switches(self):
        self.panel._chk_db_enabled.setChecked(True)
        self.assertFalse(self.panel._join_widget.isEnabled())

        self.panel._cmb_join_table.setCurrentText("detail d")
        self.panel._cmb_join_left.setCurrentText("m.id")
        self.panel._cmb_join_right.setCurrentText("d.id")
        binding = self.panel._collect_db_binding()
        self.assertEqual(binding.joins, [])

        self.panel._chk_use_joins.setChecked(True)
        self.assertTrue(self.panel._join_widget.isEnabled())

        binding = self.panel._collect_db_binding()
        self.assertEqual(binding.joins[0]["table"], "detail d")

    def test_metadata_populates_editable_identifier_choices(self):
        self.panel._metadata_provider = lambda _key: {
            "production": ["id", "station_id", "output"],
            "station": ["id", "name"],
        }
        self.panel._refresh_db_metadata()
        self.panel._cmb_table.setCurrentText("production")
        self.panel._cmb_join_table.setCurrentText("station")

        self.assertGreaterEqual(self.panel._cmb_table.findText("production"), 0)
        self.assertGreaterEqual(self.panel._cmb_field.findText("output"), 0)
        self.assertGreaterEqual(self.panel._cmb_join_left.findText("production.id"), 0)
        self.assertGreaterEqual(self.panel._cmb_join_right.findText("station.name"), 0)

        self.panel._cmb_field.setCurrentText("calculated_value")
        self.assertEqual(self.panel._cmb_field.currentText(), "calculated_value")


if __name__ == "__main__":
    unittest.main()
