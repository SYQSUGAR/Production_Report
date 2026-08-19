"""模板编辑页左右独立属性栏。"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QPushButton

from ui.style_panel import StylePanel
from models.template_model import CellStyle


<<<<<<< HEAD
def _hide_removed_toolbox_page(toolbox, index: int):
    """Remove a toolbox page and explicitly hide the retained widget.

    QToolBox.removeItem() only removes the item entry; Qt keeps the page widget
    parented and it may remain visible on top of the remaining page.
    """
    page = toolbox.widget(index)
    if page is None:
        return
    toolbox.removeItem(index)
    page.hide()


=======
>>>>>>> fb7ea564cf4c851b81e6014b781451d387cb7801
class StyleOnlyPanel(StylePanel):
    """左侧：仅保留字体、颜色、边框、对齐和数字格式。"""

    def __init__(self, template, parent=None):
        super().__init__(template, parent=parent, metadata_provider=None)
        self.setMinimumWidth(285)
        self.setMaximumWidth(360)

        if self._toolbox.count() > 1:
<<<<<<< HEAD
            _hide_removed_toolbox_page(self._toolbox, 1)
=======
            self._toolbox.removeItem(1)
>>>>>>> fb7ea564cf4c851b81e6014b781451d387cb7801
        self._hide_legacy_actions()

        self._lbl_nf_db_lock.hide()
        self._cmb_number_cat.setEnabled(True)
        self._nf_sub_widget.setEnabled(True)
        self._nf_grp.setToolTip("")

<<<<<<< HEAD
    def set_current_selection(self, scope: str, row: int, col: int):
        """左侧只同步样式，不读取隐藏的数据库表单。"""
        self._set_selection_context(scope, row, col)
        self._load_style_for_current_scope()

=======
>>>>>>> fb7ea564cf4c851b81e6014b781451d387cb7801
    def _hide_legacy_actions(self):
        for group in self.findChildren(QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

    def _on_number_cat_changed(self, idx: int):
        categories = ["常规", "数值", "日期", "百分比", "文本", "自定义"]
        cat = categories[idx] if 0 <= idx < len(categories) else "常规"
        self._nf_decimals_row.hide()
        self._cmb_nf_date.hide()
        self._txt_nf_custom.hide()
        self._lbl_nf_hint.hide()
        if cat in ("数值", "百分比"):
            self._nf_decimals_row.show()
        elif cat == "日期":
            self._cmb_nf_date.show()
        elif cat == "自定义":
            self._txt_nf_custom.show()
        else:
            self._lbl_nf_hint.setText("无任何特定数字格式" if cat == "常规" else "文本格式")
            self._lbl_nf_hint.show()
        if not self._suppress_update:
            self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _on_number_format_changed(self):
        if not self._suppress_update:
            self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _update_db_ui_state(self):
        super()._update_db_ui_state()
        self._cmb_number_cat.setEnabled(True)
        self._nf_sub_widget.setEnabled(True)
        self._lbl_nf_db_lock.hide()
        self._nf_grp.setToolTip("")


class DatabaseBindingPanel(StylePanel):
    """右侧：数据库绑定和 SQL；多选时整批应用并一次撤销。"""

    database_binding_changed = pyqtSignal()

    def __init__(self, template, parent=None, metadata_provider=None, undo_manager=None):
        self._undo_manager = undo_manager
        super().__init__(template, parent=parent, metadata_provider=metadata_provider)
        self.setMinimumWidth(380)
        self.setMaximumWidth(520)

        if self._toolbox.count() > 0:
<<<<<<< HEAD
            _hide_removed_toolbox_page(self._toolbox, 0)
        self._hide_legacy_actions()

    def set_current_selection(self, scope: str, row: int, col: int):
        """右侧只同步数据库绑定，不读取隐藏的样式表单。"""
        self._set_selection_context(scope, row, col)
        self._load_db_binding()

=======
            self._toolbox.removeItem(0)
        self._hide_legacy_actions()

>>>>>>> fb7ea564cf4c851b81e6014b781451d387cb7801
    def _hide_legacy_actions(self):
        for group in self.findChildren(QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

    def refresh_template(self, template):
        self._template = template

    def refresh_sql_preview(self):
        self._update_sql_preview()

    def _target_cells(self):
        cells = list(dict.fromkeys(self._selected_cells or []))
        if len(cells) > 1:
            return cells
        if self._current_row >= 0 and self._current_col >= 0:
            return [(self._current_row, self._current_col)]
        return []

    def _apply_db_binding(self):
        """应用数据库配置到当前选区；多格修改作为一个撤销批次。"""
        if self._suppress_update:
            return
        targets = self._target_cells()
        if not targets:
            return

        new_binding = self._collect_db_binding()
        changes = []
        for row, col in targets:
            cd = self._template.get_cell_data(row, col)
            old_dict = cd.to_dict()
            new_cd = type(cd).from_dict(old_dict)
            new_cd.query_binding = type(new_binding).from_dict(new_binding.to_dict())
            new_dict = new_cd.to_dict()
            if old_dict == new_dict:
                continue
            self._template.set_cell_data(row, col, new_cd)
            changes.append(("cell_data", row, col, old_dict, new_dict))

        if changes and self._undo_manager is not None:
            self._undo_manager.record_batch(changes)
        self._update_sql_preview()
        if changes:
            self.database_binding_changed.emit()

    def _update_sql_preview(self):
        """SQL 预览使用模板阶段的真实时间占位符，而不是假日期。"""
        qb = self._collect_db_binding()
        if not qb.enabled:
            self._lbl_sql_preview.setText("（未启用数据库绑定）")
            self._lbl_sql_validate.setText("")
            return

        sql = qb.build_sql()
        if not sql:
            self._lbl_sql_preview.setText("（请填写字段/数据表或 SQL 语句）")
            self._lbl_sql_validate.setText("")
            return

        self._lbl_sql_preview.setText(sql)
        err = qb.validate_time_sql() or self._validate_sql(sql)
        if err:
            self._lbl_sql_validate.setText(f"⚠ {err}")
            self._lbl_sql_validate.setStyleSheet("color:#D93025;")
        else:
            if qb.time_binding.enabled and "{start_time}" in sql:
                self._lbl_sql_validate.setText(
                    "✓ SQL 模板有效；{start_time}/{end_time} 将在生成报表时由预览时间替换"
                )
            else:
                self._lbl_sql_validate.setText("✓ SQL 语法正确")
            self._lbl_sql_validate.setStyleSheet("color:#188038;")

    def _generate_manual_sql(self):
        qb = self._collect_db_binding()
        qb.sql_mode = "builder"
        sql = qb.build_sql()
        if sql:
            self._txt_custom_sql.blockSignals(True)
            self._txt_custom_sql.setPlainText(sql)
            self._txt_custom_sql.blockSignals(False)
            self._apply_db_binding()
            self._update_sql_preview()
