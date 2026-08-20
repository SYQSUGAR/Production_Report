import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QToolBar

from ui.workspace_window import WorkspaceWindow


class WorkspaceSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WorkspaceWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_workspace_constructs_without_crash(self):
        self.assertIsNotNone(self.window._editor)
        self.assertIsNotNone(self.window._style_panel)
        self.assertIsNotNone(self.window._db_panel)
        self.assertIsNotNone(self.window._time_panel)
        self.assertIsNotNone(self.window._report_preview)

    def test_top_menu_and_toolbar_are_owned_by_workspace(self):
        menu_texts = [a.text().replace("&", "") for a in self.window.menuBar().actions()]
        self.assertIn("文件(F)", menu_texts)
        self.assertIn("编辑(E)", menu_texts)
        self.assertIn("数据库(D)", menu_texts)

        toolbar = self.window.findChild(QToolBar, "")
        toolbars = self.window.findChildren(QToolBar)
        workspace_bars = [tb for tb in toolbars if tb.parent() is self.window]
        self.assertTrue(workspace_bars)
        action_texts = [a.text() for a in workspace_bars[0].actions() if a.text()]
        self.assertIn("撤销", action_texts)
        self.assertIn("恢复", action_texts)
        self.assertIn("复制", action_texts)
        self.assertIn("粘贴", action_texts)

    def test_side_panels_do_not_cross_construct_controls(self):
        self.assertTrue(hasattr(self.window._style_panel, "_nf_grp"))
        self.assertFalse(hasattr(self.window._style_panel, "_chk_db_enabled"))
        self.assertTrue(hasattr(self.window._db_panel, "_chk_db_enabled"))
        self.assertFalse(hasattr(self.window._db_panel, "_nf_grp"))


if __name__ == "__main__":
    unittest.main()
