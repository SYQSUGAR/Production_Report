import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from models.template_model import TemplateModel, CellData
from models.db_config import QueryBinding, QueryType
from ui.editor_side_panels import DatabaseBindingPanel, StyleOnlyPanel


class EditorSidePanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.template = TemplateModel(3, 3)
        self.style_panel = StyleOnlyPanel(self.template)
        self.db_panel = DatabaseBindingPanel(self.template)
        self.style_panel.show()
        self.db_panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.style_panel.close()
        self.db_panel.close()

    def test_each_panel_constructs_only_its_own_controls(self):
        self.assertEqual(self.style_panel._toolbox.count(), 1)
        self.assertTrue(hasattr(self.style_panel, "_nf_grp"))
        self.assertFalse(hasattr(self.style_panel, "_chk_db_enabled"))
        self.assertFalse(hasattr(self.style_panel, "_builder_widget"))

        self.assertEqual(self.db_panel._toolbox.count(), 1)
        self.assertTrue(hasattr(self.db_panel, "_chk_db_enabled"))
        self.assertTrue(hasattr(self.db_panel, "_builder_widget"))
        self.assertFalse(hasattr(self.db_panel, "_nf_grp"))
        self.assertFalse(hasattr(self.db_panel, "_cmb_number_cat"))

    def test_each_side_loads_only_its_own_state(self):
        style_loads = []
        db_loads = []
        self.style_panel._load_style_for_current_scope = lambda: style_loads.append(True)
        self.style_panel.set_current_selection("cell", 1, 2)
        self.assertEqual(style_loads, [True])

        self.db_panel._load_db_binding = lambda: db_loads.append(True)
        self.db_panel.set_current_selection("cell", 1, 2)
        self.assertEqual(db_loads, [True])

    def test_multi_cell_patch_only_changes_requested_database_property(self):
        first = QueryBinding(
            enabled=True,
            query_type=QueryType.AGGREGATE,
            table_name="production_a",
            field_name="old_a",
            aggregate_func="SUM",
            filters=[{"field": "workshop", "op": "=", "value": "A"}],
        )
        second = QueryBinding(
            enabled=False,
            query_type=QueryType.SINGLE,
            table_name="production_b",
            field_name="old_b",
            aggregate_func="AVG",
            filters=[{"field": "workshop", "op": "=", "value": "B"}],
        )
        self.template.set_cell_data(0, 0, CellData(query_binding=first))
        self.template.set_cell_data(1, 1, CellData(query_binding=second))
        self.db_panel.set_selected_cells([(0, 0), (1, 1)])
        self.db_panel._current_row = 0
        self.db_panel._current_col = 0

        self.db_panel._apply_db_patch({"field_name": "new_value"})

        qb1 = self.template.get_cell_data(0, 0).query_binding
        qb2 = self.template.get_cell_data(1, 1).query_binding
        self.assertEqual(qb1.field_name, "new_value")
        self.assertEqual(qb2.field_name, "new_value")
        self.assertEqual(qb1.table_name, "production_a")
        self.assertEqual(qb2.table_name, "production_b")
        self.assertEqual(qb1.filters[0]["value"], "A")
        self.assertEqual(qb2.filters[0]["value"], "B")
        self.assertTrue(qb1.enabled)
        self.assertFalse(qb2.enabled)
        self.assertEqual(qb1.query_type, QueryType.AGGREGATE)
        self.assertEqual(qb2.query_type, QueryType.SINGLE)

    def test_multi_cell_enabled_patch_does_not_replace_other_query_settings(self):
        first = QueryBinding(enabled=False, table_name="a", field_name="fa")
        second = QueryBinding(enabled=False, table_name="b", field_name="fb")
        self.template.set_cell_data(0, 0, CellData(query_binding=first))
        self.template.set_cell_data(0, 1, CellData(query_binding=second))
        self.db_panel.set_selected_cells([(0, 0), (0, 1)])

        self.db_panel._apply_db_patch({"enabled": True})

        qb1 = self.template.get_cell_data(0, 0).query_binding
        qb2 = self.template.get_cell_data(0, 1).query_binding
        self.assertTrue(qb1.enabled)
        self.assertTrue(qb2.enabled)
        self.assertEqual((qb1.table_name, qb1.field_name), ("a", "fa"))
        self.assertEqual((qb2.table_name, qb2.field_name), ("b", "fb"))

    def test_metadata_is_only_requested_by_explicit_refresh(self):
        calls = []

        def provider(key):
            calls.append(key)
            return {
                "production_daily": ["record_time", "output", "workshop"],
                "equipment": ["id", "name"],
            }

        panel = DatabaseBindingPanel(self.template, metadata_provider=provider)
        panel.show()
        self.app.processEvents()
        try:
            panel._current_row = 0
            panel._current_col = 0
            panel._chk_db_enabled.setChecked(True)
            self.app.processEvents()
            self.assertEqual(calls, [])

            self.assertTrue(panel.refresh_database_metadata())
            self.assertEqual(calls, ["default"])
            self.assertIn("production_daily", [
                panel._cmb_table.itemText(i) for i in range(panel._cmb_table.count())
            ])
            self.assertIn("数据库已刷新", panel._lbl_metadata_state.text())
        finally:
            panel.close()

    def test_all_database_identifier_inputs_are_searchable_dropdowns(self):
        combos = [
            self.db_panel._cmb_table,
            self.db_panel._cmb_field,
            self.db_panel._cmb_join_table,
            self.db_panel._cmb_join_left,
            self.db_panel._cmb_join_right,
            self.db_panel._filter_rows[0]["field_combo"],
        ]
        for combo in combos:
            self.assertTrue(combo.isEditable())
            self.assertIsNotNone(combo.completer())
            self.assertEqual(combo.completer().filterMode(), Qt.MatchFlag.MatchContains)
            self.assertTrue(combo.property("identifier_combo_ready"))

    def test_date_placeholder_and_side_refresh_button_are_hidden(self):
        self.db_panel.show()
        self.app.processEvents()
        self.assertTrue(self.db_panel._txt_date_ph.isHidden())
        self.assertTrue(self.db_panel._btn_refresh_metadata.isHidden())
        labels = self.db_panel.findChildren(QLabel)
        date_labels = [label for label in labels if label.text().startswith("日期占位符")]
        self.assertTrue(date_labels)
        self.assertTrue(all(label.isHidden() for label in date_labels))
        self.assertEqual(self.db_panel._lbl_metadata_state.text(), "未读取到数据库")


if __name__ == "__main__":
    unittest.main()
