import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QComboBox

from ui.workspace_window import WorkspaceWindow
from ui.workspace_behaviors import PresetSaveDialog


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

    def test_database_menu_has_explicit_refresh_database_action(self):
        self.assertIsNotNone(self.window._act_refresh_database)
        self.assertEqual(self.window._act_refresh_database.text(), "刷新数据库")

        db_menu = None
        for action in self.window._global_menu_bar.actions():
            menu = action.menu()
            if menu and menu.title().replace("&", "").startswith("数据库"):
                db_menu = menu
                break
        self.assertIsNotNone(db_menu)
        self.assertIn("刷新数据库", [a.text() for a in db_menu.actions()])

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

    def test_time_field_is_searchable_database_field_dropdown(self):
        self.assertIsInstance(self.window._time_panel._time_field, QComboBox)
        self.assertTrue(self.window._time_panel._time_field.isEditable())
        self.assertIsNotNone(self.window._time_panel._time_field.completer())
        self.assertEqual(
            self.window._time_panel._time_field.completer().filterMode(),
            Qt.MatchFlag.MatchContains,
        )

    def test_sidebar_outer_toggles_and_inner_resize_handles_are_fixed(self):
        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()

        splitter = self.window._main_splitter
        left_strip = self.window._left_toggle_strip
        right_strip = self.window._right_toggle_strip

        self.assertIsNot(left_strip.parentWidget(), splitter)
        self.assertIsNot(right_strip.parentWidget(), splitter)
        self.assertEqual(left_strip.width(), 16)
        self.assertEqual(right_strip.width(), 16)
        self.assertTrue(left_strip.isVisible())
        self.assertTrue(right_strip.isVisible())

        self.assertEqual(splitter.count(), 3)
        self.assertEqual(splitter.handleWidth(), 5)
        self.assertIsNotNone(splitter.handle(1))
        self.assertIsNotNone(splitter.handle(2))
        self.assertEqual(splitter.handle(1).cursor().shape(), Qt.CursorShape.SplitHCursor)
        self.assertEqual(splitter.handle(2).cursor().shape(), Qt.CursorShape.SplitHCursor)

        splitter.set_side_collapsed("left", True)
        self.app.processEvents()
        self.assertTrue(splitter.side_collapsed("left"))
        self.assertLessEqual(splitter.sizes()[0], 1)
        self.assertTrue(left_strip.isVisible())

        splitter.set_side_collapsed("left", False)
        self.app.processEvents()
        self.assertFalse(splitter.side_collapsed("left"))
        self.assertGreater(splitter.sizes()[0], 1)

        splitter.set_side_collapsed("right", True)
        self.app.processEvents()
        self.assertTrue(splitter.side_collapsed("right"))
        self.assertLessEqual(splitter.sizes()[2], 1)
        self.assertTrue(right_strip.isVisible())

        splitter.set_side_collapsed("right", False)
        self.app.processEvents()
        self.assertFalse(splitter.side_collapsed("right"))
        self.assertGreater(splitter.sizes()[2], 1)

    def test_side_panel_headers_match_requested_hierarchy(self):
        self.assertEqual(self.window._style_group.title(), "字体 / 样式 / 边框")
        self.assertEqual(self.window._db_group.title(), "数据库绑定与时间条件")

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

    def test_preset_dialog_uses_name_field_as_only_save_decision(self):
        dlg = PresetSaveDialog(self.window._editor._template, self.window)
        try:
            self.assertEqual(dlg._name.placeholderText(), "请输入预设名称")
            self.assertFalse(hasattr(dlg, "_replace_btn"))
            self.assertGreater(dlg._list.count(), 0)

            item = dlg._list.item(0)
            name, _kind = item.data(Qt.ItemDataRole.UserRole)
            dlg._list.setCurrentItem(item)
            self.app.processEvents()
            self.assertEqual(dlg._name.text(), name)
        finally:
            dlg.close()


if __name__ == "__main__":
    unittest.main()
