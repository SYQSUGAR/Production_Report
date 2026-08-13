import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableWidgetSelectionRange
from PyQt6.QtTest import QTest

from models.template_model import CellData, CellStyle, TemplateModel
from ui.main_window import MainWindow


class ClipboardSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        template = TemplateModel(6, 6)
        for r, row in enumerate((("A", "B"), ("C", "D"))):
            for c, value in enumerate(row):
                template.set_cell_data(r, c, CellData(static_text=value))
                template.set_cell_style(r, c, CellStyle(bold=True, bg_color="#D6E4F0"))
        self.window._apply_loaded_template(template, "test")
        self.table = self.window._preview

    def tearDown(self):
        self.window.close()

    def select_range(self, top, left, bottom, right):
        self.table.select_cells([(r, c) for r in range(top, bottom + 1)
                                 for c in range(left, right + 1)], (top, left))
        self.app.processEvents()

    def test_multi_cell_copy_expands_from_single_anchor(self):
        self.select_range(0, 0, 1, 1)
        self.window._copy()
        self.select_range(2, 2, 2, 2)
        self.window._paste()
        values = [[self.window._template.get_cell_data(r, c).static_text
                   for c in range(2, 4)] for r in range(2, 4)]
        self.assertEqual(values, [["A", "B"], ["C", "D"]])
        self.assertTrue(self.window._template.get_effective_style(3, 3).bold)

    def test_click_target_then_ctrl_v_uses_clicked_cell_as_anchor(self):
        self.window.show()
        self.select_range(0, 0, 1, 1)
        self.window._copy()
        self.app.processEvents()
        target = self.table.visualItemRect(self.table.item(3, 2)).center()
        QTest.mouseClick(self.table.viewport(), Qt.MouseButton.LeftButton, pos=target)
        self.app.processEvents()
        self.assertEqual((self.table.currentRow(), self.table.currentColumn()), (3, 2))
        QTest.keyClick(self.table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.app.processEvents()
        values = [[self.window._template.get_cell_data(r, c).static_text
                   for c in range(2, 4)] for r in range(3, 5)]
        self.assertEqual(values, [["A", "B"], ["C", "D"]])

    def test_two_dimensional_rectangle_copy(self):
        for r in range(3):
            for c in range(4):
                self.window._template.set_cell_data(r, c, CellData(static_text=f"{r},{c}"))
        self.select_range(0, 1, 2, 3)
        self.assertEqual(len(self.table.get_selected_cells()), 9)
        self.window._copy()
        self.select_range(3, 0, 3, 0)
        self.window._paste_values()
        self.assertEqual(self.window._template.get_cell_data(3, 0).static_text, "0,1")
        self.assertEqual(self.window._template.get_cell_data(5, 2).static_text, "2,3")

    def test_merged_cell_copy_preserves_merge_content_and_format(self):
        self.window._template.add_merge_range(0, 0, 0, 2)
        self.window._template.set_cell_data(0, 0, CellData(static_text="合并标题"))
        merged_style = CellStyle(font_size=18, bold=True, bg_color="#123456",
                                 border_bottom="double", border_line_style="double")
        self.window._template.set_cell_style(0, 0, merged_style)
        self.table.refresh_all()
        # Qt 将合并格任意位置归一到左上主格，逻辑选区再扩展为完整范围。
        self.table.select_cells([(0, 0)], (0, 0))
        self.assertEqual(self.table.get_selected_cells(), [(0, 0), (0, 1), (0, 2)])
        self.window._copy()
        self.select_range(2, 1, 2, 1)
        self.window._paste()
        pasted = self.window._template.get_merge_range(2, 1)
        self.assertIsNotNone(pasted)
        self.assertEqual((pasted.top_row, pasted.bottom_row, pasted.left_col, pasted.right_col),
                         (2, 2, 1, 3))
        self.assertEqual(self.window._template.get_cell_data(2, 1).static_text, "合并标题")
        self.assertEqual(self.window._template.get_effective_style(2, 1).bg_color, "#123456")
        self.window._undo()
        self.assertIsNone(self.window._template.get_merge_range(2, 1))
        self.window._redo()
        self.assertIsNotNone(self.window._template.get_merge_range(2, 1))

    def test_three_by_three_with_merge_click_anchor_ignores_stale_selection(self):
        self.window._template.add_merge_range(0, 0, 0, 1)
        self.window._template.set_cell_data(0, 0, CellData(static_text="合并"))
        self.window._template.set_cell_style(0, 0, CellStyle(bold=True, bg_color="#778899"))
        for r in range(3):
            for c in range(3):
                if (r, c) not in ((0, 0), (0, 1)):
                    self.window._template.set_cell_data(r, c, CellData(static_text=f"{r}{c}"))
        self.table.refresh_all()
        self.select_range(0, 0, 2, 2)
        self.window._copy()

        self.window.show()
        self.app.processEvents()
        target = self.table.visualItemRect(self.table.item(3, 2)).center()
        QTest.mouseClick(self.table.viewport(), Qt.MouseButton.LeftButton, pos=target)
        self.app.processEvents()
        # 即便底层仍残留多个 selectedIndexes，也必须以最后点击格作为单一锚点。
        self.table.setRangeSelected(QTableWidgetSelectionRange(4, 4, 5, 5), True)
        QTest.keyClick(self.table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.app.processEvents()
        self.assertEqual(self.window._template.get_cell_data(3, 2).static_text, "合并")
        pasted = self.window._template.get_merge_range(3, 2)
        self.assertIsNotNone(pasted)
        self.assertEqual((pasted.top_row, pasted.bottom_row, pasted.left_col, pasted.right_col),
                         (3, 3, 2, 3))
        self.assertEqual(self.window._template.get_cell_data(5, 4).static_text, "22")
        self.assertEqual(self.window._template.get_effective_style(3, 2).bg_color, "#778899")

    def test_single_cell_copy_fills_selected_area_and_preserves_selection(self):
        self.select_range(0, 0, 0, 0)
        self.window._copy()
        self.select_range(2, 1, 4, 3)
        self.window._paste()
        self.assertEqual(len(self.table.get_selected_cells()), 9)
        self.assertTrue(all(self.window._template.get_cell_data(r, c).static_text == "A"
                            for r in range(2, 5) for c in range(1, 4)))

    def test_larger_target_repeats_source_pattern(self):
        self.select_range(0, 0, 1, 1)
        self.window._copy()
        self.select_range(2, 0, 5, 3)
        self.window._paste_values()
        self.assertEqual(self.window._template.get_cell_data(4, 2).static_text, "A")
        self.assertEqual(self.window._template.get_cell_data(5, 3).static_text, "D")

    def test_format_paste_does_not_change_content(self):
        self.select_range(0, 0, 0, 0)
        self.window._copy_format()
        self.window._template.set_cell_data(3, 3, CellData(static_text="保留"))
        self.select_range(3, 3, 3, 3)
        self.window._paste_format()
        self.assertEqual(self.window._template.get_cell_data(3, 3).static_text, "保留")
        self.assertEqual(self.window._template.get_effective_style(3, 3).bg_color, "#D6E4F0")

    def test_style_refresh_keeps_selection(self):
        self.select_range(1, 1, 2, 2)
        before = set(self.table.get_selected_cells())
        self.window._template.set_cell_style(1, 1, CellStyle(fg_color="#FF0000"))
        self.window._on_style_changed()
        self.assertEqual(set(self.table.get_selected_cells()), before)

    def test_batch_font_size_changes_only_font_size_and_is_one_undo_step(self):
        original = CellStyle(font_family="宋体", font_size=10, bold=True,
                             fg_color="#112233", bg_color="#D6E4F0",
                             border_top="dashed", border_line_style="dashed",
                             border_width=2, number_format="percent")
        for r, c in ((2, 2), (2, 3), (3, 2), (3, 3)):
            self.window._template.set_cell_style(r, c, original)
        self.select_range(2, 2, 3, 3)
        selected_before = set(self.table.get_selected_cells())
        self.window._quick_apply_style(font_size=18)
        for r, c in selected_before:
            style = self.window._template.cell_styles[(r, c)]
            self.assertEqual(style.font_size, 18)
            self.assertEqual(style.font_family, "宋体")
            self.assertTrue(style.bold)
            self.assertEqual(style.fg_color, "#112233")
            self.assertEqual(style.bg_color, "#D6E4F0")
            self.assertEqual(style.border_top, "dashed")
            self.assertEqual(style.number_format, "percent")
        self.assertEqual(set(self.table.get_selected_cells()), selected_before)

        self.window._undo()
        self.assertTrue(all(self.window._template.cell_styles[pos].font_size == 10
                            for pos in selected_before))
        self.assertEqual(set(self.table.get_selected_cells()), selected_before)
        self.window._redo()
        self.assertTrue(all(self.window._template.cell_styles[pos].font_size == 18
                            for pos in selected_before))

    def test_left_panel_incremental_style_isolated_and_undoable(self):
        base = CellStyle(font_family="微软雅黑", font_size=12, italic=True,
                         fg_color="#010203", bg_color="#EEEEEE",
                         border_bottom="double", border_line_style="double",
                         number_format="decimal_2")
        for pos in ((1, 1), (1, 2)):
            self.window._template.set_cell_style(*pos, base)
        self.table.select_cells([(1, 1), (1, 2)], (1, 1))
        self.window._style_panel.set_selected_cells([(1, 1), (1, 2)])
        self.app.processEvents()
        self.window._style_panel._apply_style(CellStyle(bg_color="#ABCDEF"))
        for pos in ((1, 1), (1, 2)):
            style = self.window._template.cell_styles[pos]
            self.assertEqual(style.bg_color, "#ABCDEF")
            self.assertEqual(style.font_family, "微软雅黑")
            self.assertEqual(style.font_size, 12)
            self.assertTrue(style.italic)
            self.assertEqual(style.fg_color, "#010203")
            self.assertEqual(style.border_bottom, "double")
            self.assertEqual(style.number_format, "decimal_2")
        self.window._undo()
        self.assertTrue(all(self.window._template.cell_styles[pos].bg_color == "#EEEEEE"
                            for pos in ((1, 1), (1, 2))))


if __name__ == "__main__":
    unittest.main()
