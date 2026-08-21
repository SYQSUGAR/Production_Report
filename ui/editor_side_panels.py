"""模板编辑页左右独立属性栏。

左侧只创建样式控件；右侧只创建数据库控件。数据库编辑采用增量 patch：
用户改了哪个属性，就只把那个属性应用到当前所有选中单元格。
"""

from copy import deepcopy

from PyQt6.QtCore import Qt, QEvent, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QPushButton, QLabel, QComboBox

from ui.style_panel import StylePanel
from models.template_model import CellStyle, CellData
from models.db_config import QueryBinding, QueryType


class _ComboPopupFilter(QObject):
    """让可输入下拉框在获得焦点/点击时自动展开。

    下拉内容来自已经缓存的数据库元数据；这里只负责本地交互，不访问数据库。
    """

    def __init__(self, combo: QComboBox, parent=None):
        super().__init__(parent or combo)
        self._combo = combo

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            QTimer.singleShot(0, self._show_popup)
        return False

    def _show_popup(self):
        if self._combo.isEnabled() and self._combo.isVisible():
            self._combo.showPopup()


class StyleOnlyPanel(StylePanel):
    """左侧：只负责字体、颜色、对齐、边框和数字格式。"""

    def _build_db_group(self):
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

    数据库元数据只在用户显式执行“数据库 → 刷新数据库”时读取一次并缓存。
    切换单元格、启用绑定、输入字段等操作都只使用缓存，不主动访问数据库。
    """

    database_binding_changed = pyqtSignal()

    def _build_style_group(self):
        return

    def __init__(self, template, parent=None, metadata_provider=None, undo_manager=None):
        self._undo_manager = undo_manager
        self._metadata_config_signature = None
        self._combo_popup_filters = []
        super().__init__(template, parent=parent, metadata_provider=metadata_provider)
        self.setMinimumWidth(380)
        self.setMaximumWidth(520)
        self._hide_legacy_actions()
        self._hide_date_placeholder_ui()
        self._prepare_identifier_combos()
        self._set_metadata_unread_state()

    def _hide_legacy_actions(self):
        for group in self.findChildren(QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()
        # 元数据刷新统一放到第一排“数据库 → 刷新数据库”，侧栏不再有第二个入口。
        if hasattr(self, "_btn_refresh_metadata"):
            self._btn_refresh_metadata.hide()

    def _hide_date_placeholder_ui(self):
        """日期占位符不再作为数据库绑定配置项展示。"""
        if hasattr(self, "_txt_date_ph"):
            self._txt_date_ph.hide()
        for label in self.findChildren(QLabel):
            if label.text().strip().startswith("日期占位符"):
                label.hide()

    def _prepare_identifier_combos(self):
        for combo in (
            self._cmb_table,
            self._cmb_field,
            self._cmb_join_table,
            self._cmb_join_left,
            self._cmb_join_right,
        ):
            self._configure_identifier_combo(combo)
        for row in self._filter_rows:
            self._configure_identifier_combo(row["field_combo"])

    def _configure_identifier_combo(self, combo: QComboBox):
        if combo.property("identifier_combo_ready"):
            return
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(completer.CompletionMode.PopupCompletion)

        line_edit = combo.lineEdit()
        popup_filter = _ComboPopupFilter(combo, combo)
        line_edit.installEventFilter(popup_filter)
        self._combo_popup_filters.append(popup_filter)

        def show_filtered_popup(_text, c=combo):
            comp = c.completer()
            if comp is not None and c.isEnabled() and c.isVisible():
                QTimer.singleShot(0, comp.complete)

        line_edit.textEdited.connect(show_filtered_popup)
        combo.setProperty("identifier_combo_ready", True)

    def set_current_selection(self, scope: str, row: int, col: int):
        self._set_selection_context(scope, row, col)
        self._load_db_binding()

    def _db_config_signature(self, template=None):
        template = template or self._template
        cfg = template.db_configs.get("default") if template else None
        if cfg is None:
            return None
        attrs = ("db_type", "host", "port", "user", "database", "charset")
        return tuple(getattr(cfg, name, None) for name in attrs)

    def refresh_template(self, template):
        """切换模板时保留同一数据库的缓存；数据源变化则只清缓存、不联网。"""
        self._template = template
        if (
            self._metadata_config_signature is not None
            and self._metadata_config_signature != self._db_config_signature(template)
        ):
            self.clear_database_metadata()

    def refresh_sql_preview(self):
        self._update_sql_preview()

    def _set_metadata_unread_state(self):
        self._lbl_metadata_state.setText("未读取到数据库")
        self._lbl_metadata_state.setStyleSheet("color:#B06000;")

    def clear_database_metadata(self):
        """清除缓存和下拉候选，但保留用户当前已经输入的文本。"""
        self._db_metadata = {}
        self._metadata_config_signature = None
        self._set_combo_choices(self._cmb_table, [])
        self._set_combo_choices(self._cmb_join_table, [])
        self._refresh_identifier_choices()
        self._set_metadata_unread_state()

    def refresh_database_metadata(self) -> bool:
        """唯一的主动数据库元数据刷新入口。"""
        provider = self._metadata_provider
        metadata = provider("default") if provider else {}
        self._db_metadata = metadata or {}
        self._metadata_config_signature = self._db_config_signature()

        tables = sorted(self._db_metadata, key=str.lower)
        self._set_combo_choices(self._cmb_table, tables)
        self._set_combo_choices(self._cmb_join_table, tables)
        self._refresh_identifier_choices()

        if not tables:
            self._set_metadata_unread_state()
            return False

        column_count = sum(len(items) for items in self._db_metadata.values())
        self._lbl_metadata_state.setText(
            f"数据库已刷新：{len(tables)} 个数据表，{column_count} 个字段"
        )
        self._lbl_metadata_state.setStyleSheet("color:#287A3D;")
        return True

    # 兼容 StylePanel 原按钮/调用名称，但不会由单元格选择自动触发。
    def _refresh_db_metadata(self):
        return self.refresh_database_metadata()

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
    # 数据库控件状态
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
        # 启用数据库绑定只改变绑定状态；绝不在这里读取数据库。
        self._update_db_ui_state()
        self._apply_db_patch({"enabled": self._chk_db_enabled.isChecked()})

    def _on_query_type_changed(self, _idx):
        self._update_db_ui_state()
        query_type = QueryType.SINGLE if self._cmb_query_type.currentIndex() == 0 else QueryType.AGGREGATE
        self._apply_db_patch({"query_type": query_type})

    def _on_optional_query_changed(self, _state):
        self._update_db_ui_state()
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
        # 日期占位符 UI 已移除，不再由侧栏修改 date_placeholder。
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

        for fr in self._filter_rows:
            if sender in (
                fr.get("field"), fr.get("field_combo"), fr.get("op"),
                fr.get("value"), fr.get("connector"),
            ):
                self._apply_db_patch({"filters": self._current_filters()})
                return

        self._apply_db_patch({"filters": self._current_filters()})

    def _on_manual_sql_changed(self):
        self._apply_db_patch({"custom_sql": self._txt_custom_sql.toPlainText().strip()})

    def _add_filter_row(self):
        super()._add_filter_row()
        if self._filter_rows:
            fr = self._filter_rows[-1]
            connector = fr.get("connector")
            if connector is not None and not connector.property("db_patch_connected"):
                connector.currentTextChanged.connect(self._on_db_config_changed)
                connector.setProperty("db_patch_connected", True)
            field_combo = fr.get("field_combo")
            if field_combo is not None:
                self._configure_identifier_combo(field_combo)

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
        qb = self._collect_db_binding()
        qb.sql_mode = "builder"
        sql = qb.build_sql()
        if sql:
            self._txt_custom_sql.blockSignals(True)
            self._txt_custom_sql.setPlainText(sql)
            self._txt_custom_sql.blockSignals(False)
            self._apply_db_patch({"custom_sql": sql})

    def _update_sql_preview(self):
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
                self._lbl_sql_validate.setText("✓ SQL 模板有效；生成报表时自动应用时间范围")
            else:
                self._lbl_sql_validate.setText("✓ SQL 语法正确")
            self._lbl_sql_validate.setStyleSheet("color:#188038;")
