"""模板编辑页左右独立属性栏。

左侧只创建样式控件；右侧只创建数据库控件。数据库编辑采用增量 patch：
用户改了哪个属性，就只把那个属性应用到当前所有选中单元格。
"""

from copy import deepcopy

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QPushButton

from ui.style_panel import StylePanel
from models.template_model import CellStyle, CellData
from models.db_config import QueryBinding, QueryType


class StyleOnlyPanel(StylePanel):
    """左侧：只负责字体、颜色、对齐、边框和数字格式。"""

    def _build_db_group(self):
        """左侧构造时就不创建数据库控件，避免隐藏控件与右侧串状态。"""
        return

    def __init__(self, template, parent=None):
        super().__init__(template, parent=parent, metadata_provider=None)
        self.setMinimumWidth(285)
        self.setMaximumWidth(360)
        self._hide_legacy_actions()

    def _hide_legacy_actions(self):
        for group in self.findChildren(QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

    def set_current_selection(self, scope: str, row: int, col: int):
        """左侧只同步样式，完全不读取数据库表单。"""
        self._set_selection_context(scope, row, col)
        self._load_style_for_current_scope()

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


class DatabaseBindingPanel(StylePanel):
    """右侧：只负责数据库绑定和 SQL。

    多选时无论是单行、单列还是多行多列，当前选中的所有单元格都是目标。
    所有编辑均采用增量 patch；例如只改字段名，就不会覆盖各单元格原有的
    表名、筛选条件、SQL、时间绑定等其他配置。
    """

    database_binding_changed = pyqtSignal()

    def _build_style_group(self):
        """右侧构造时就不创建样式控件，彻底消除左右控件重叠。"""
        return

    def __init__(self, template, parent=None, metadata_provider=None, undo_manager=None):
        self._undo_manager = undo_manager
        super().__init__(template, parent=parent, metadata_provider=metadata_provider)
        self.setMinimumWidth(380)
        self.setMaximumWidth(520)
        self._hide_legacy_actions()

    def _hide_legacy_actions(self):
        for group in self.findChildren(QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

    def set_current_selection(self, scope: str, row: int, col: int):
        """右侧只同步数据库绑定，完全不读取样式表单。"""
        self._set_selection_context(scope, row, col)
        self._load_db_binding()

    def refresh_template(self, template):
        self._template = template

    def refresh_sql_preview(self):
        self._update_sql_preview()

    # ==================================================================
    # 多选目标与增量 patch
    # ==================================================================
    def _target_cells(self):
        cells = list(dict.fromkeys(self._selected_cells or []))
        if cells:
            return cells
        if self._current_row >= 0 and self._current_col >= 0:
            return [(self._current_row, self._current_col)]
        return []

    def _apply_db_patch(self, patch: dict):
        """只修改 patch 中明确给出的 QueryBinding 属性。

        一次操作作用于整个当前选区，并只生成一个 undo batch。
        """
        if self._suppress_update or not patch:
            return
        targets = self._target_cells()
        if not targets:
            return

        changes = []
        for row, col in targets:
            cd = self._template.get_cell_data(row, col)
            old_dict = cd.to_dict()
            new_cd = CellData.from_dict(old_dict)
            qb = new_cd.query_binding
            if qb is None:
                qb = QueryBinding()

            for key, value in patch.items():
                if hasattr(qb, key):
                    setattr(qb, key, deepcopy(value))

            new_cd.query_binding = qb
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

    def _current_filters(self):
        return deepcopy(self._collect_db_binding().filters)

    def _current_joins(self):
        return deepcopy(self._collect_db_binding().joins)

    # ==================================================================
    # 数据库控件状态：不再访问任何样式/数字格式控件
    # ==================================================================
    def _update_db_ui_state(self):
        enabled = self._chk_db_enabled.isChecked()
        self._cmb_sql_mode.setEnabled(enabled)
        self._chk_sql_sync.setEnabled(enabled)
        self._builder_widget.setEnabled(enabled)
        self._manual_widget.setEnabled(enabled)
        self._agg_widget.setVisible(self._cmb_query_type.currentIndex() == 1)
        self._chk_use_joins.setEnabled(enabled)
        use_joins = enabled and self._chk_use_joins.isChecked()
        self._lbl_joins.setEnabled(use_joins)
        self._join_widget.setEnabled(use_joins)

    # ==================================================================
    # 各控件只 patch 自己负责的属性
    # ==================================================================
    def _on_db_enabled_changed(self, _state):
        self._update_db_ui_state()
        if self._chk_db_enabled.isChecked() and not self._db_metadata:
            self._refresh_db_metadata()
        self._apply_db_patch({"enabled": self._chk_db_enabled.isChecked()})

    def _on_query_type_changed(self, _idx):
        self._update_db_ui_state()
        query_type = QueryType.SINGLE if self._cmb_query_type.currentIndex() == 0 else QueryType.AGGREGATE
        self._apply_db_patch({"query_type": query_type})

    def _on_optional_query_changed(self, _state):
        self._update_db_ui_state()
        # 关闭关联表时只清空 joins；开启后使用当前填写的 join 配置。
        joins = self._current_joins() if self._chk_use_joins.isChecked() else []
        self._apply_db_patch({"joins": joins})

    def _on_db_config_changed(self, *_args):
        if self._suppress_update:
            return
        sender = self.sender()

        if sender is self._txt_table:
            self._apply_db_patch({"table_name": self._txt_table.text().strip()})
            return
        if sender is self._txt_field:
            self._apply_db_patch({"field_name": self._txt_field.text().strip()})
            return
        if sender is self._txt_date_ph:
            self._apply_db_patch({"date_placeholder": self._txt_date_ph.text().strip()})
            return
        if sender is self._cmb_aggregate:
            self._apply_db_patch({"aggregate_func": self._cmb_aggregate.currentText()})
            return
        if sender is self._chk_sql_sync:
            self._apply_db_patch({"sync_modes": self._chk_sql_sync.isChecked()})
            return

        if sender in (
            self._cmb_join_type, self._cmb_join_table,
            self._cmb_join_left, self._cmb_join_right,
        ):
            self._apply_db_patch({"joins": self._current_joins()})
            return

        # 条件行的字段/运算符/值/连接符，以及删除条件操作，都只影响 filters。
        for fr in self._filter_rows:
            if sender in (
                fr.get("field"), fr.get("field_combo"), fr.get("op"),
                fr.get("value"), fr.get("connector"),
            ):
                self._apply_db_patch({"filters": self._current_filters()})
                return

        # _remove_filter_row() 内部直接调用时 sender 可能是删除按钮或 None。
        self._apply_db_patch({"filters": self._current_filters()})

    def _on_manual_sql_changed(self):
        self._apply_db_patch({"custom_sql": self._txt_custom_sql.toPlainText().strip()})

    def _add_filter_row(self):
        """补上连接符变化信号，使 AND/OR 修改也能增量应用。"""
        super()._add_filter_row()
        if self._filter_rows:
            fr = self._filter_rows[-1]
            connector = fr.get("connector")
            if connector is not None and not connector.property("db_patch_connected"):
                connector.currentTextChanged.connect(self._on_db_config_changed)
                connector.setProperty("db_patch_connected", True)

    # ==================================================================
    # SQL 模式/互通
    # ==================================================================
    def _on_sql_mode_changed(self, idx: int):
        mode = "manual" if idx == 1 else "builder"
        patch = {"sql_mode": mode}

        if mode == "manual":
            self._builder_widget.hide()
            self._manual_widget.show()
            if self._chk_sql_sync.isChecked() or not self._txt_custom_sql.toPlainText().strip():
                qb = self._collect_db_binding()
                qb.sql_mode = "builder"
                sql = qb.build_sql()
                if sql:
                    self._txt_custom_sql.blockSignals(True)
                    self._txt_custom_sql.setPlainText(sql)
                    self._txt_custom_sql.blockSignals(False)
                    patch["custom_sql"] = sql
        else:
            self._manual_widget.hide()
            self._builder_widget.show()
            sql = self._txt_custom_sql.toPlainText().strip()
            if sql and self._chk_sql_sync.isChecked():
                old_suppress = self._suppress_update
                self._suppress_update = True
                try:
                    parsed = self._parse_sql_to_filters(sql)
                finally:
                    self._suppress_update = old_suppress
                if parsed:
                    collected = self._collect_db_binding()
                    patch.update({
                        "table_name": collected.table_name,
                        "field_name": collected.field_name,
                        "query_type": collected.query_type,
                        "aggregate_func": collected.aggregate_func,
                        "filters": deepcopy(collected.filters),
                    })

        self._update_db_ui_state()
        if not self._suppress_update:
            self._apply_db_patch(patch)
        else:
            self._update_sql_preview()

    def _generate_manual_sql(self):
        """显式生成 SQL 时，只更新 custom_sql，不覆盖其他查询属性。"""
        qb = self._collect_db_binding()
        qb.sql_mode = "builder"
        sql = qb.build_sql()
        if sql:
            self._txt_custom_sql.blockSignals(True)
            self._txt_custom_sql.setPlainText(sql)
            self._txt_custom_sql.blockSignals(False)
            self._apply_db_patch({"custom_sql": sql})

    def _update_sql_preview(self):
        """模板阶段显示时间占位符；运行时再由报表预览替换。"""
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
