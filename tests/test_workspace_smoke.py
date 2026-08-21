import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel

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
        self.assertIsNotNone(self.window._file_behavior)

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
        self.assertTrue(self.window._global_menu_bar.isVisible())
        self.assertIs(self.window._global_menu_bar.parent(), self.window.centralWidget())

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(self.window._global_menu_bar.isVisible())

        self.window._tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertTrue(self.window._global_menu_bar.isVisible())

    def test_template_toolbar_is_template_page_only(self):
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

    def test_sidebars_can_collapse_to_hover_edge_and_expand_again(self):
        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()

        self.assertFalse(self.window._left_side.collapsed)
        self.window._left_side.set_collapsed(True)
        self.app.processEvents()
        self.assertTrue(self.window._left_side.collapsed)
        self.assertFalse(self.window._style_group.isVisible())
        self.assertLessEqual(self.window._left_side.maximumWidth(), 18)

        self.window._left_side.set_collapsed(False)
        self.app.processEvents()
        self.assertFalse(self.window._left_side.collapsed)
        self.assertTrue(self.window._style_group.isVisible())

        self.assertFalse(self.window._right_side.collapsed)
        self.window._right_side.set_collapsed(True)
        self.app.processEvents()
        self.assertTrue(self.window._right_side.collapsed)
        self.assertFalse(self.window._db_group.isVisible())
        self.window._right_side.set_collapsed(False)
        self.app.processEvents()
        self.assertFalse(self.window._right_side.collapsed)

    def test_side_panel_headers_match_requested_hierarchy(self):
        self.assertEqual(self.window._style_group.title(), "字体 / 样式 / 边框")
        self.assertEqual(self.window._db_group.title(), "数据库绑定与时间条件")

        # 数据库栏不再显示“当前选中范围”。
        visible_group_titles = [
            g.title() for g in self.window._db_panel.findChildren(QGroupBox)
            if not g.isHidden()
        ]
        self.assertNotIn("当前选中范围", visible_group_titles)

        labels = [label.text() for label in self.window._db_panel.findChildren(QLabel)]
        self.assertIn("数据库绑定", labels)
        time_labels = [label.text() for label in self.window._time_panel.findChildren(QLabel)]
        self.assertIn("时间绑定", time_labels)

    def test_dirty_snapshot_detects_template_change(self):
        behavior = self.window._file_behavior
        self.assertFalse(behavior.is_dirty())
        cd = self.window._editor._template.get_cell_data(0, 0)
        cd.static_text = "dirty-test"
        self.window._editor._template.set_cell_data(0, 0, cd)
        self.assertTrue(behavior.is_dirty())
        behavior.mark_clean()
        self.assertFalse(behavior.is_dirty())


if __name__ == "__main__":
    unittest.main()
