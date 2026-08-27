"""数据库绑定交互收尾：数据返回分组、受控预览、关联完整性与布局。"""


def install_database_binding_v4_refine():
    from copy import deepcopy

    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (
        QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
        QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QTableWidget,
        QTableWidgetItem, QVBoxLayout, QWidget,
    )

    if getattr(esp, "_database_binding_v4_refine_installed", False):
        return
    esp._database_binding_v4_refine_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_move_join = cls._move_join_v2
    previous_remove_join = cls._remove_join_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2
    previous_update_state = cls._update_db_ui_state

    def _find_label(panel, text):
        for label in panel.findChildren(QLabel):
            if label.text().strip() == text:
                return label
        return None

    def _selected_databases(panel):
        return list(getattr(panel._template, "selected_databases", []) or [])

    def _resolve_table(panel, text):
        text = (text or "").strip()
        if not text:
            return "", ""
        lookup = getattr(panel, "_table_lookup_v3", {}) or {}
        if text in lookup:
            return lookup[text]
        meta = getattr(panel, "_all_db_metadata", {}) or {}
        matches = [(db, text) for db in _selected_databases(panel) if text in (meta.get(db, {}) or {})]
        return matches[0] if len(matches) == 1 else ("", text)

    def _display_table(panel, db, table):
        return (getattr(panel, "_table_reverse_v3", {}) or {}).get((db, table), table)

    def _quote_table(panel, db, table):
        cfg = panel._template.db_configs.get("default")
        db_type = (getattr(cfg, "db_type", "mysql") or "mysql").lower()
        if db_type == "mysql":
            qdb = db.replace("`", "``")
            qtable = table.replace("`", "``")
            return f"`{qdb}`.`{qtable}`" if db else f"`{qtable}`"
        parts = table.split(".", 1)
        schema, raw = (parts[0], parts[1]) if len(parts) == 2 else ("dbo", table)
        return ".".join(f"[{part.replace(']', ']]')}]" for part in (db, schema, raw) if part)

    def _close_choice_popup(combo):
        if combo is None or not combo.isEditable() or combo.property("v4_close_choice"):
            return

        def close(c=combo):
            c.hidePopup()
            comp = c.completer()
            if comp is not None and comp.popup() is not None:
                comp.popup().hide()

        combo.activated.connect(lambda *_: QTimer.singleShot(0, close))
        comp = combo.completer()
        if comp is not None:
            comp.activated.connect(lambda *_: QTimer.singleShot(0, close))
        combo.setProperty("v4_close_choice", True)

    def _condition_complete(cond):
        return bool(cond["left"].currentText().strip() and cond["right"].currentText().strip())

    def _row_complete(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return False
        index = rows.index(row)
        if index == 0:
            left = row.get("left_table_v3")
            if left is None or not left.currentText().strip():
                return False
        if not row["table"].currentText().strip():
            return False
        conditions = list(row.get("conditions", []) or [])
        return bool(conditions) and all(_condition_complete(cond) for cond in conditions)

    def _chain_complete(panel, through_index=None):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if not rows:
            return False
        end = len(rows) if through_index is None else through_index + 1
        return all(_row_complete(panel, row) for row in rows[:end])

    def _refresh_action_states(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        for row in rows:
            conditions = list(row.get("conditions", []) or [])
            can_add_condition = bool(conditions) and _condition_complete(conditions[-1])
            if row.get("add_condition") is not None:
                row["add_condition"].setEnabled(can_add_condition)
                row["add_condition"].setToolTip(
                    "当前关联条件填写完整后可继续添加条件" if not can_add_condition else "添加一条 AND / OR 关联条件"
                )
        can_add_join = bool(rows) and _row_complete(panel, rows[-1])
        if hasattr(panel, "_btn_add_join_v2"):
            panel._btn_add_join_v2.setEnabled(can_add_join)
            panel._btn_add_join_v2.setToolTip(
                "当前关联填写完整后可继续添加关联" if not can_add_join else "继续关联下一张表"
            )

    def _move_group_buttons_right(panel, row):
        if row.get("v4_group_controls"):
            return
        row["v4_group_controls"] = True
        top = row["widget"].layout().itemAt(0).layout()
        for button in (row["up"], row["down"], row["remove"]):
            top.removeWidget(button)
        top.addStretch(1)
        top.addWidget(row["up"])
        top.addWidget(row["down"])
        top.addWidget(row["remove"])
        row["type"].setMaximumWidth(120)
        row["up"].setToolTip("整组关联上移")
        row["down"].setToolTip("整组关联下移")
        row["remove"].setToolTip("删除整组关联")

    def _hide_alias(panel, row):
        row["alias"].hide()
        label = row.get("alias_label_v3")
        if label is not None:
            label.hide()

    def _wire_condition(panel, row, cond):
        if cond.get("v4_wired"):
            return
        cond["v4_wired"] = True
        cond["remove"].setToolTip("删除这一条关联条件")
        for combo in (cond["left"], cond["right"], cond["connector"]):
            if combo is not None:
                combo.currentTextChanged.connect(lambda *_: _condition_edited(panel, row))
                _close_choice_popup(combo)

    def _wire_row(panel, row):
        if not row.get("v4_wired"):
            row["v4_wired"] = True
            if row.get("left_table_v3") is not None:
                row["left_table_v3"].currentTextChanged.connect(lambda *_: _row_edited(panel, row))
                _close_choice_popup(row["left_table_v3"])
            row["table"].currentTextChanged.connect(lambda *_: _row_edited(panel, row))
            _close_choice_popup(row["table"])
            row["type"].currentTextChanged.connect(lambda *_: _row_edited(panel, row))
        _move_group_buttons_right(panel, row)
        _hide_alias(panel, row)
        for cond in list(row.get("conditions", []) or []):
            _wire_condition(panel, row, cond)

    def _refresh_pair_selector(panel, preferred=None):
        window = getattr(panel, "_data_preview_v3", None)
        if not isinstance(window, _AssociationPreview):
            return
        rows = list(getattr(panel, "_join_rows", []) or [])
        current = window.pair_combo.currentIndex() if preferred is None else preferred
        window.pair_combo.blockSignals(True)
        window.pair_combo.clear()
        for index, row in enumerate(rows):
            if index == 0:
                left_name = row.get("left_table_v3").currentText().strip() if row.get("left_table_v3") is not None else ""
            else:
                left_name = "当前合并结果"
            right_name = row["table"].currentText().strip()
            window.pair_combo.addItem(f"第{index + 1}对：{left_name or '未选择'} ↔ {right_name or '未选择'}")
        if rows:
            window.pair_combo.setCurrentIndex(max(0, min(current, len(rows) - 1)))
        window.pair_combo.blockSignals(False)
        window.pair_row.setVisible(panel._radio_join_v3.isChecked())

    def _ensure_connection(panel, force=False):
        editor = getattr(panel, "_editor", None)
        if editor is None:
            return None, None
        cfg = editor._template.db_configs.get("default")
        if cfg is None:
            return None, None
        if not editor._db_handler.is_connected("default") and not editor._db_handler.connect(cfg, "default"):
            if force:
                QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "数据库连接失败")
            return None, None
        return editor, cfg

    def _fill_table(table_widget, result):
        if result is None:
            return False
        headers, rows = result
        # 同名字段仍然全部展示，重复列追加序号，避免视觉上误认为是同一列。
        counts = {}
        for name in headers:
            counts[name] = counts.get(name, 0) + 1
        seen = {}
        display_headers = []
        for name in headers:
            if counts.get(name, 0) <= 1:
                display_headers.append(name)
            else:
                seen[name] = seen.get(name, 0) + 1
                display_headers.append(f"{name} ({seen[name]})")
        table_widget.clear()
        table_widget.setColumnCount(len(display_headers))
        table_widget.setHorizontalHeaderLabels(display_headers)
        table_widget.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table_widget.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        table_widget.resizeColumnsToContents()
        return True

    def _query_table(panel, db, table, limit, force=False):
        editor, cfg = _ensure_connection(panel, force)
        if editor is None or not db or not table:
            return None
        qualified = _quote_table(panel, db, table)
        if (getattr(cfg, "db_type", "mysql") or "mysql").lower() == "sqlserver":
            sql = f"SELECT TOP {limit} * FROM {qualified}"
        else:
            sql = f"SELECT * FROM {qualified} LIMIT {limit}"
        switch_db = db if len(_selected_databases(panel)) == 1 else ""
        return editor._db_handler.execute_rows(sql, "default", switch_db)

    def _partial_join_query(panel, pair_index, include_current, limit, force=False):
        editor, cfg = _ensure_connection(panel, force)
        if editor is None:
            return None
        qb = panel._collect_db_binding()
        count = pair_index + 1 if include_current else pair_index
        qb = deepcopy(qb)
        qb.joins = list(qb.joins[:count])
        if not qb.joins:
            return _query_table(panel, qb.database_name, qb.table_name, limit, force)
        if qb.validate_joins():
            return None
        sql = qb.build_join_preview_sql(limit, cfg.db_type)
        switch_db = qb.database_name if len(_selected_databases(panel)) == 1 else ""
        return editor._db_handler.execute_rows(sql, "default", switch_db)

    class _AssociationPreview(QDialog):
        """兼容 V3 预览接口，同时增加逐对关联的左/右/合并三块预览。"""

        def __init__(self, panel):
            super().__init__(panel.window())
            self.panel = panel
            self.setWindowTitle("数据案例预览")
            self.resize(1280, 760)
            self.setModal(False)
            root = QVBoxLayout(self)

            self.info = QLabel("尚未选择数据表")
            self.info.setWordWrap(True)
            root.addWidget(self.info)

            self.pair_row = QWidget()
            pair_lay = QHBoxLayout(self.pair_row)
            pair_lay.setContentsMargins(0, 0, 0, 0)
            pair_lay.addWidget(QLabel("当前关联:"))
            self.pair_combo = QComboBox()
            pair_lay.addWidget(self.pair_combo, 1)
            root.addWidget(self.pair_row)
            self.pair_combo.currentIndexChanged.connect(lambda *_: _refresh_pair_preview(self.panel, False))

            tools = QHBoxLayout()
            tools.addWidget(QLabel("显示行数:"))
            self.limit = QComboBox(); self.limit.addItems(["10", "20", "50", "100"]); self.limit.setCurrentText("20")
            self.refresh_button = QPushButton("刷新")
            self.refresh_button.clicked.connect(lambda: _refresh_visible_preview(self.panel, True))
            tools.addWidget(self.limit); tools.addWidget(self.refresh_button); tools.addStretch(1)
            root.addLayout(tools)

            self.pair_splitter = QSplitter(Qt.Orientation.Horizontal)
            left_group = QGroupBox("左侧数据")
            left_lay = QVBoxLayout(left_group)
            self.left_info = QLabel("未选择")
            self.left_table = QTableWidget()
            self.left_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.left_table.setAlternatingRowColors(True)
            left_lay.addWidget(self.left_info); left_lay.addWidget(self.left_table, 1)
            right_group = QGroupBox("右侧数据")
            right_lay = QVBoxLayout(right_group)
            self.right_info = QLabel("未选择")
            self.right_table = QTableWidget()
            self.right_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.right_table.setAlternatingRowColors(True)
            right_lay.addWidget(self.right_info); right_lay.addWidget(self.right_table, 1)
            self.pair_splitter.addWidget(left_group); self.pair_splitter.addWidget(right_group)
            root.addWidget(self.pair_splitter, 1)

            self.merged_group = QGroupBox("合并结果")
            merged_lay = QVBoxLayout(self.merged_group)
            self.table = QTableWidget()  # 保持 V3 _refresh_preview 的兼容属性。
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setAlternatingRowColors(True)
            merged_lay.addWidget(self.table)
            root.addWidget(self.merged_group, 1)

            self.status = QLabel("")
            self.status.setStyleSheet("color:#666;")
            root.addWidget(self.status)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self._user_hide)
            root.addWidget(buttons)

        def _user_hide(self):
            self.panel._preview_user_opened_v4 = False
            super().hide()

        def closeEvent(self, event):
            self.panel._preview_user_opened_v4 = False
            event.ignore()
            super().hide()

        # V3 的自动刷新仍会调用 show/raise_/activateWindow；未由用户打开时一律忽略。
        def show(self):
            if getattr(self.panel, "_preview_user_opened_v4", False):
                super().show()

        def raise_(self):
            if getattr(self.panel, "_preview_user_opened_v4", False):
                super().raise_()

        def activateWindow(self):
            if getattr(self.panel, "_preview_user_opened_v4", False):
                super().activateWindow()

        def set_join_mode(self, join_mode):
            self.pair_row.setVisible(join_mode)
            self.pair_splitter.setVisible(join_mode)
            self.merged_group.setTitle("合并结果" if join_mode else "数据表预览")

    def _refresh_pair_preview(panel, force=False):
        window = getattr(panel, "_data_preview_v3", None)
        if not isinstance(window, _AssociationPreview) or not getattr(panel, "_preview_user_opened_v4", False):
            return False
        rows = list(getattr(panel, "_join_rows", []) or [])
        if not rows:
            return False
        pair_index = max(0, min(window.pair_combo.currentIndex(), len(rows) - 1))
        row = rows[pair_index]
        limit = int(window.limit.currentText())

        if pair_index == 0:
            left_combo = row.get("left_table_v3")
            ldb, ltable = _resolve_table(panel, left_combo.currentText() if left_combo is not None else "")
            left_result = _query_table(panel, ldb, ltable, limit, force)
            window.left_info.setText(_display_table(panel, ldb, ltable) if ltable else "未选择左表")
        else:
            left_result = _partial_join_query(panel, pair_index, False, limit, force) if _chain_complete(panel, pair_index - 1) else None
            window.left_info.setText(f"前 {pair_index} 对关联的当前合并结果")
        if left_result is not None:
            _fill_table(window.left_table, left_result)

        rdb, rtable = _resolve_table(panel, row["table"].currentText())
        right_result = _query_table(panel, rdb, rtable, limit, force)
        window.right_info.setText(_display_table(panel, rdb, rtable) if rtable else "未选择右表")
        if right_result is not None:
            _fill_table(window.right_table, right_result)

        if _chain_complete(panel, pair_index):
            merged = _partial_join_query(panel, pair_index, True, limit, force)
            if merged is not None:
                _fill_table(window.table, merged)
                window.status.setText(f"第 {pair_index + 1} 对关联信息完整，已更新本对合并结果")
        else:
            window.status.setText("当前这对关联尚未填写完整；合并结果保持上一次有效内容")
        return True

    def _refresh_visible_preview(panel, force=False):
        window = getattr(panel, "_data_preview_v3", None)
        if not isinstance(window, _AssociationPreview) or not getattr(panel, "_preview_user_opened_v4", False):
            return False
        join_mode = panel._radio_join_v3.isChecked()
        window.set_join_mode(join_mode)
        if join_mode:
            _refresh_pair_selector(panel)
            return _refresh_pair_preview(panel, force)
        # 单表继续调用 V3 的正式预览查询；自定义窗口的 table 属性与其兼容。
        return panel._preview_join_result_v2()

    def _open_preview(panel):
        panel._preview_user_opened_v4 = True
        window = panel._data_preview_v3
        window.set_join_mode(panel._radio_join_v3.isChecked())
        _refresh_pair_selector(panel)
        QDialog.show(window)
        if panel._radio_join_v3.isChecked():
            _refresh_pair_preview(panel, True)
        else:
            panel._preview_join_result_v2()

    def _select_pair_for_row(panel, row):
        window = getattr(panel, "_data_preview_v3", None)
        rows = list(getattr(panel, "_join_rows", []) or [])
        if isinstance(window, _AssociationPreview) and row in rows:
            window.pair_combo.blockSignals(True)
            window.pair_combo.setCurrentIndex(rows.index(row))
            window.pair_combo.blockSignals(False)

    def _condition_edited(panel, row):
        _refresh_action_states(panel)
        _select_pair_for_row(panel, row)
        if getattr(panel, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_pair_preview(panel, False))

    def _row_edited(panel, row):
        _refresh_action_states(panel)
        _refresh_pair_selector(panel, (getattr(panel, "_join_rows", []) or []).index(row) if row in (getattr(panel, "_join_rows", []) or []) else 0)
        _select_pair_for_row(panel, row)
        if getattr(panel, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_pair_preview(panel, False))

    def _refresh_all_rows(panel):
        for row in list(getattr(panel, "_join_rows", []) or []):
            _wire_row(panel, row)
        _refresh_action_states(panel)
        _refresh_pair_selector(panel)
        for combo in (panel._cmb_table, panel._cmb_field):
            _close_choice_popup(combo)
        for fr in list(getattr(panel, "_filter_rows", []) or []):
            _close_choice_popup(fr.get("field_combo"))

    def _build_return_group(panel):
        builder = panel._builder_widget.layout()
        old_query_label = _find_label(panel, "查询类型:")
        if old_query_label is not None:
            old_query_label.hide()
        if getattr(panel, "_return_row_v3", None) is not None:
            panel._return_row_v3.hide()

        group = QGroupBox("数据返回")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 8, 6, 6)
        return_row = QHBoxLayout()
        return_row.addWidget(QLabel("返回字段:"))
        return_row.addWidget(panel._cmb_field, 1)
        layout.addLayout(return_row)
        query_row = QHBoxLayout()
        query_row.addWidget(QLabel("查询类型:"))
        query_row.addWidget(panel._cmb_query_type, 1)
        layout.addLayout(query_row)
        layout.addWidget(panel._agg_widget)
        join_index = builder.indexOf(panel._join_group_v2)
        builder.insertWidget(join_index + 1 if join_index >= 0 else builder.count(), group)
        panel._data_return_group_v4 = group

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        self._preview_user_opened_v4 = False
        # 在 V3 初始化产生的延迟自动刷新执行前替换预览对象；其 show() 会尊重用户打开状态。
        old_preview = getattr(self, "_data_preview_v3", None)
        if old_preview is not None:
            old_preview.hide(); old_preview.deleteLater()
        self._data_preview_v3 = _AssociationPreview(self)

        # “表关联”模式本身就是唯一开关，不再保留旧的第二个关联复选框。
        self._chk_use_joins.hide()
        self._lbl_joins.hide()
        self._join_widget.hide()

        _build_return_group(self)
        try:
            self._btn_preview_join_v2.clicked.disconnect()
        except TypeError:
            pass
        self._btn_preview_join_v2.setText("打开 / 刷新预览")
        self._btn_preview_join_v2.setToolTip("只有主动打开后才会随表和关联配置自动刷新；关闭后不会自行弹出")
        self._btn_preview_join_v2.clicked.connect(lambda: _open_preview(self))

        _refresh_all_rows(self)
        _close_choice_popup(self._cmb_table)
        _close_choice_popup(self._cmb_field)

    def add_condition(self, row, data=None):
        # 用户点击时：最后一条条件没填完就不允许继续增加；加载旧配置时 data 会绕过此限制。
        if data is None and row.get("conditions") and not _condition_complete(row["conditions"][-1]):
            _refresh_action_states(self)
            return
        result = previous_add_condition(self, row, data)
        if row.get("conditions"):
            _wire_condition(self, row, row["conditions"][-1])
        _refresh_action_states(self)
        return result

    def add_join(self, data=None):
        rows = list(getattr(self, "_join_rows", []) or [])
        # 与“添加条件”一致：当前最后一组完整后才允许新增下一组；模板恢复不受影响。
        if data is None and rows and not _row_complete(self, rows[-1]):
            _refresh_action_states(self)
            return
        result = previous_add_join(self, data)
        _refresh_all_rows(self)
        return result

    def move_join(self, row, delta):
        result = previous_move_join(self, row, delta)
        _refresh_all_rows(self)
        if getattr(self, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_pair_preview(self, False))
        return result

    def remove_join(self, row):
        result = previous_remove_join(self, row)
        _refresh_all_rows(self)
        if getattr(self, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_pair_preview(self, False))
        return result

    def load_binding(self):
        result = previous_load(self)
        _refresh_all_rows(self)
        # 切换单元格只更新预览内容；预览未打开时绝不会自行打开。
        if getattr(self, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_visible_preview(self, False))
        return result

    def join_changed(self, *args):
        result = previous_join_changed(self, *args)
        _refresh_all_rows(self)
        if getattr(self, "_preview_user_opened_v4", False):
            QTimer.singleShot(80, lambda: _refresh_pair_preview(self, False))
        return result

    def update_state(self):
        result = previous_update_state(self)
        if hasattr(self, "_data_return_group_v4"):
            self._data_return_group_v4.setEnabled(self._chk_db_enabled.isChecked())
        _refresh_action_states(self)
        return result

    cls.__init__ = panel_init
    cls._add_join_condition_v2 = add_condition
    cls._add_join_row_v2 = add_join
    cls._move_join_v2 = move_join
    cls._remove_join_v2 = remove_join
    cls._load_db_binding = load_binding
    cls._on_join_changed_v2 = join_changed
    cls._update_db_ui_state = update_state
