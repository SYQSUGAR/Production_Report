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

    @staticmethod
    def _menu_titles(bar):
        return [a.text().replace("&", "") for a in bar.actions()]

    def test_global_file_database_bar_is_single_and_above_tabs(self):
        titles = self._menu_titles(self.window._global_menu_bar)
        self.assertTrue(any(t.startswith("文件") for t in titles))
        self.assertTrue(any(t.startswith("数据库") for t in titles))
        self.assertFalse(any(t.startswith("编辑") for t in titles))

        # 全局菜单只有一份，父级是整个 workspace，而不是某一个页签页面。
        self.assertTrue(self.window._global_menu_bar.isVisible())
        self.assertIs(self.window._global_menu_bar.parent(), self.window.centralWidget())

        # 切换到任一页面，全局菜单始终存在。
        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(self.window._global_menu_bar.isVisible())

        self.window._tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertTrue(self.window._global_menu_bar.isVisible())

    def test_template_toolbar_is_template_page_only(self):
        # 默认在预览页，模板编辑工具栏不显示。
        self.assertFalse(self.window._template_toolbar.isVisible())

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(self.window._template_toolbar.isVisible())

        self.window._tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertFalse(self.window._template_toolbar.isVisible())

    def test_template_toolbar_keeps_original_action_order(self):
        source = None
        for tb in self.window._editor.findChildren(type(self.window._template_toolbar)):
            if tb.windowTitle() == "主工具栏" and tb is not self.window._template_toolbar:
                source = tb
                break
        self.assertIsNotNone(source)
        self.assertEqual(
            [a.text() for a in self.window._template_toolbar.actions()],
            [a.text() for a in source.actions()],
        )

    def test_global_refresh_resyncs_report_preview_and_editor_side_panels(self):
        preview_calls = []
        sync_calls = []
        original_preview = self.window._report_preview.sync_template
        original_sync = self.window._sync_side_panel_templates
        self.window._report_preview.sync_template = lambda: preview_calls.append(True)
        self.window._sync_side_panel_templates = lambda: sync_calls.append(True)
        try:
            self.window._refresh_after_global_action()
        finally:
            self.window._report_preview.sync_template = original_preview
            self.window._sync_side_panel_templates = original_sync
        self.assertEqual(preview_calls, [True])
        self.assertEqual(sync_calls, [True])

    def test_side_panels_do_not_cross_construct_controls(self):
        self.assertTrue(hasattr(self.window._style_panel, "_nf_grp"))
        self.assertFalse(hasattr(self.window._style_panel, "_chk_db_enabled"))
        self.assertTrue(hasattr(self.window._db_panel, "_chk_db_enabled"))
        self.assertFalse(hasattr(self.window._db_panel, "_nf_grp"))


if __name__ == "__main__":
    unittest.main()
