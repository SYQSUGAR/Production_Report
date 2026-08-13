import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from export.excel_importer import ExcelImporter
from ui.preview_table import PreviewTable
from ui.main_window import _UndoManager


REAL_REPORT = r"E:\1工作\2026\2.平台插件\1.搭建过程\生产运行日报(2026年06月27日) (1).xlsx"


class RealReportImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_real_spreadsheetml_import_and_visual_render(self):
        template = ExcelImporter.import_file(REAL_REPORT)
        self.assertGreaterEqual(template.rows, 48)
        self.assertEqual(template.cols, 20)
        self.assertGreater(len(template.cell_styles), 400)
        self.assertGreater(len(template.merge_ranges), 100)
        bordered = sum(bool(style.border_top or style.border_bottom or style.border_left or style.border_right)
                       for style in template.cell_styles.values())
        self.assertGreater(bordered, 100)
        table = PreviewTable(template)
        table.resize(1400, 850)
        table.show()
        self.app.processEvents()
        screenshot = os.environ.get("REPORT_PREVIEW_OUTPUT")
        if screenshot:
            self.assertTrue(table.grab().save(screenshot))
            self.assertGreater(os.path.getsize(screenshot), 10_000)

    def test_undo_manager_preserves_change_order(self):
        manager = _UndoManager()
        manager.record_change(0, 0, "原值", "第一次")
        manager.record_change(0, 0, "第一次", "第二次")
        first_undo = manager.undo()
        self.assertEqual(first_undo[0][3], "第一次")
        second_undo = manager.undo()
        self.assertEqual(second_undo[0][3], "原值")
        first_redo = manager.redo()
        self.assertEqual(first_redo[0][4], "第一次")


if __name__ == "__main__":
    unittest.main()
