import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

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

    def test_preview_is_first_and_default_tab(self):
        self.assertEqual(self.window._tabs.count(), 2)
        self.assertEqual(self.window._tabs.tabText(0), "报表预览")
        self.assertEqual(self.window._tabs.tabText(1), "模板编辑")
        self.assertEqual(self.window._tabs.currentIndex(), 0)

    def test_edit_menu_and_toolbar_live_inside_template_page_only(self):
        # Workspace 顶层不再承载模板编辑菜单/工具栏。
        self.assertFalse(self.window.menuBar().isVisible())

        self.assertEqual(
            [a.text().replace("&", "") for a in self.window._template_menu_bar.actions()],
            [a.text().replace("&", "") for a in self.window._editor.menuBar().actions()],
        )
        self.assertEqual(
            [a.text() for a in self.window._template_toolbar.actions()],
            [a.text() for tb in self.window._editor.findChildren(type(self.window._template_toolbar))
             if tb.windowTitle() == "主工具栏" and tb is not self.window._template_toolbar
             for a in tb.actions()],
        )

        # 默认在预览页时，模板页整体不可见，因此两排编辑操作也不可见。
        self.assertFalse(self.window._template_menu_bar.isVisible())
        self.assertFalse(self.window._template_toolbar.isVisible())

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(self.window._template_menu_bar.isVisible())
        self.assertTrue(self.window._template_toolbar.isVisible())

    def test_side_panels_do_not_cross_construct_controls(self):
        self.assertTrue(hasattr(self.window._style_panel, "_nf_grp"))
        self.assertFalse(hasattr(self.window._style_panel, "_chk_db_enabled"))
        self.assertTrue(hasattr(self.window._db_panel, "_chk_db_enabled"))
        self.assertFalse(hasattr(self.window._db_panel, "_nf_grp"))


if __name__ == "__main__":
    unittest.main()
