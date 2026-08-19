import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from models.template_model import TemplateModel
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

    def test_removed_pages_do_not_overlay_the_remaining_panel(self):
        self.assertEqual(self.style_panel._toolbox.count(), 1)
        self.assertFalse(self.style_panel._builder_widget.isVisible())
        self.assertTrue(self.style_panel._nf_grp.isVisible())

        self.assertEqual(self.db_panel._toolbox.count(), 1)
        self.assertFalse(self.db_panel._nf_grp.isVisible())
        self.assertTrue(self.db_panel._builder_widget.isVisible())

    def test_each_side_loads_only_its_own_state(self):
        style_loads = []
        db_loads = []
        self.style_panel._load_style_for_current_scope = lambda: style_loads.append(True)
        self.style_panel._load_db_binding = lambda: db_loads.append(True)
        self.style_panel.set_current_selection("cell", 1, 2)
        self.assertEqual(style_loads, [True])
        self.assertEqual(db_loads, [])

        style_loads.clear()
        db_loads.clear()
        self.db_panel._load_style_for_current_scope = lambda: style_loads.append(True)
        self.db_panel._load_db_binding = lambda: db_loads.append(True)
        self.db_panel.set_current_selection("cell", 1, 2)
        self.assertEqual(style_loads, [])
        self.assertEqual(db_loads, [True])


if __name__ == "__main__":
    unittest.main()
