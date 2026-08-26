"""统一数据库绑定搜索输入与单表/表关联数据案例预览状态。"""


def install_database_binding_v7_unified_interaction():
    from copy import deepcopy

    import ui.editor_side_panels as esp
    import ui.time_binding_panel as tbp
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QComboBox, QDialog, QTableWidgetItem

    from ui.search_combo_behavior import configure_search_combo

    if getattr(esp, "_database_binding_v7_unified_interaction_installed", False):
        return
    esp._database_binding_v7_unified_interaction_installed = True

    cls = esp.DatabaseBindingPanel
    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_add_filter = cls._add_filter_row_v2
    previous_move_join = cls._move_join_v2
    previous_remove_join = cls._remove_join_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2

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
        return matches[0] if len(matches) == 1 else ("", "")

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

    def _ensure_connection(panel, force=False):
        editor = getattr(panel, "_editor", None)
        if editor is None:
            return None, None
        cfg = editor._template.db_configs.get("default")
        if cfg is None:
            return None, None
        if not editor._db_handler.is_connected("default"):
            if not editor._db_handler.connect(cfg, "default"):
                if force:
                    try:
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "数据库连接失败")
                    except Exception:
                        pass
                return None, None
        return editor, cfg

    def _clear_table(widget):
        if widget is None:
            return
        widget.clear()
        widget.setRowCount(0)
        widget.setColumnCount(0)

    def _fill_table(widget, result):
        if widget is None:
            return False
        if result is None:
            _clear_table(widget)
            return False
        headers, rows = result
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
        widget.clear()
        widget.setColumnCount(len(display_headers))
        widget.setHorizontalHeaderLabels(display_headers)
        widget.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                widget.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        widget.resizeColumnsToContents()
        return True

    def _query_table(panel, db, table, limit, force=False):
        if not db or not table:
            return None
        editor, cfg = _ensure_connection(panel, force)
        if editor is None:
            return None
        qualified = _quote_table(panel, db, table)
        db_type = (getattr(cfg, "db_type", "mysql") or "mysql").lower()
        sql = f"SELECT TOP {limit} * FROM {qualified}" if db_type == "sqlserver" else f"SELECT * FROM {qualified} LIMIT {limit}"
        switch_db = db if len(_selected_databases(panel)) == 1 else ""
        return editor._db_handler.execute_rows(sql, "default", switch_db)

    def _condition_complete(cond):
        return bool(cond.get("left") and cond.get("right") and cond["left"].currentText().strip() and cond["right"].currentText().strip())

    def _row_complete(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return False
        idx = rows.index(row)
        if idx == 0:
            left = row.get("left_table_v3")
            if left is None or not left.currentText().strip() or not _resolve_table(panel, left.currentText())[1]:
                return False
        if not row.get("table") or not row["table"].currentText().strip() or not _resolve_table(panel, row["table"].currentText())[1]:
            return False
        conditions = list(row.get("conditions", []) or [])
        return bool(conditions) and all(_condition_complete(c) for c in conditions)

    def _chain_complete(panel, through_index):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if through_index < 0:
            return True
        if through_index >= len(rows):
            return False
        return all(_row_complete(panel, row) for row in rows[:through_index + 1])

    def _partial_join_query(panel, pair_index, include_current, limit, force=False):
        editor, cfg = _ensure_connection(panel, force)
        if editor is None:
            return None
        qb = deepcopy(panel._collect_db_binding())
        count = pair_index + 1 if include_current else pair_index
        qb.joins = list(qb.joins[:count])
        if count == 0:
            return _query_table(panel, qb.database_name, qb.table_name, limit, force)
        if qb.validate_joins():
            return None
        sql = qb.build_join_preview_sql(limit, cfg.db_type)
        switch_db = qb.database_name if len(_selected_databases(panel)) == 1 else ""
        return editor._db_handler.execute_rows(sql, "default", switch_db)

    def _apply_search_behavior(panel):
        # 当前数据库绑定区域里所有 editable 下拉框统一接管；动态新增控件也会在 wrapper 后再执行。
        for combo in panel.findChildren(QComboBox):
            if combo.isEditable():
                configure_search_combo(combo)

    def _wire_preview_row(panel, row):
        if row.get("v7_preview_wired"):
            # 新增条件时仍需检查新 condition。
            pass
        else:
            row["v7_preview_wired"] = True
            if row.get("left_table_v3") is not None:
                row["left_table_v3"].currentTextChanged.connect(lambda *_: _schedule_preview(panel))
            if row.get("table") is not None:
                row["table"].currentTextChanged.connect(lambda *_: _schedule_preview(panel))
            if row.get("type") is not None:
                row["type"].currentTextChanged.connect(lambda *_: _schedule_preview(panel))
        for cond in list(row.get("conditions", []) or []):
            if cond.get("v7_preview_wired"):
                continue
            cond["v7_preview_wired"] = True
            for key in ("left", "right", "connector"):
                combo = cond.get(key)
                if combo is not None:
                    combo.currentTextChanged.connect(lambda *_: _schedule_preview(panel))

    def _wire_preview_inputs(panel):
        if not getattr(panel, "_v7_base_preview_wired", False):
            panel._v7_base_preview_wired = True
            panel._cmb_table.currentTextChanged.connect(lambda *_: _schedule_preview(panel))
            panel._radio_single_v3.toggled.connect(lambda *_: _schedule_preview(panel))
            panel._radio_join_v3.toggled.connect(lambda *_: _schedule_preview(panel))
        for row in list(getattr(panel, "_join_rows", []) or []):
            _wire_preview_row(panel, row)

    def _refresh_pair_selector(panel, preferred=None):
        window = getattr(panel, "_data_preview_v3", None)
        if window is None or not hasattr(window, "pair_combo"):
            return
        rows = list(getattr(panel, "_join_rows", []) or [])
        current = window.pair_combo.currentIndex() if preferred is None else preferred
        window.pair_combo.blockSignals(True)
        window.pair_combo.clear()
        for idx, row in enumerate(rows):
            if idx == 0:
                left = row.get("left_table_v3")
                left_name = left.currentText().strip() if left is not None else ""
            else:
                left_name = "当前合并结果"
            right_name = row["table"].currentText().strip() if row.get("table") is not None else ""
            window.pair_combo.addItem(f"第{idx + 1}对：{left_name or '未选择'} ↔ {right_name or '未选择'}")
        if rows:
            window.pair_combo.setCurrentIndex(max(0, min(current, len(rows) - 1)))
        window.pair_combo.blockSignals(False)

    def _refresh_single_preview(panel, force=False):
        window = panel._data_preview_v3
        window.setWindowTitle("单表数据预览")
        if hasattr(window, "set_join_mode"):
            window.set_join_mode(False)
        if hasattr(window, "pair_row"):
            window.pair_row.hide()
        if hasattr(window, "pair_splitter"):
            window.pair_splitter.hide()

        text = panel._cmb_table.currentText().strip()
        db, table = _resolve_table(panel, text)
        if not db or not table:
            _clear_table(window.table)
            window.info.setText("当前数据表：未选择")
            window.status.setText("请选择数据表")
            return False

        limit = int(window.limit.currentText()) if hasattr(window, "limit") else 20
        result = _query_table(panel, db, table, limit, force)
        if result is None:
            _clear_table(window.table)
            window.info.setText(f"当前数据表：{_display_table(panel, db, table)}")
            window.status.setText("数据读取失败" if force else "暂无可显示数据")
            return False
        _fill_table(window.table, result)
        window.info.setText(f"当前数据表：{_display_table(panel, db, table)}")
        window.status.setText(f"显示 {len(result[1])} 行；切换单表后自动同步当前表")
        return True

    def _refresh_join_preview(panel, force=False):
        window = panel._data_preview_v3
        window.setWindowTitle("表关联数据预览")
        if hasattr(window, "set_join_mode"):
            window.set_join_mode(True)
        if hasattr(window, "pair_row"):
            window.pair_row.show()
        if hasattr(window, "pair_splitter"):
            window.pair_splitter.show()

        rows = list(getattr(panel, "_join_rows", []) or [])
        _refresh_pair_selector(panel)
        if not rows:
            _clear_table(window.left_table)
            _clear_table(window.right_table)
            _clear_table(window.table)
            window.left_info.setText("未选择左表")
            window.right_info.setText("未选择右表")
            window.info.setText("尚未添加表关联")
            window.status.setText("请添加关联")
            return False

        pair_index = max(0, min(window.pair_combo.currentIndex(), len(rows) - 1))
        row = rows[pair_index]
        limit = int(window.limit.currentText()) if hasattr(window, "limit") else 20
        window.info.setText(f"当前查看第 {pair_index + 1} 对关联；配置到哪，预览到哪")

        # 左侧：第一对显示左表；后续显示前序完整合并结果。
        if pair_index == 0:
            left_combo = row.get("left_table_v3")
            ldb, ltable = _resolve_table(panel, left_combo.currentText() if left_combo is not None else "")
            if ldb and ltable:
                left_result = _query_table(panel, ldb, ltable, limit, force)
                _fill_table(window.left_table, left_result)
                window.left_info.setText(_display_table(panel, ldb, ltable))
            else:
                _clear_table(window.left_table)
                window.left_info.setText("未选择左表")
        else:
            if _chain_complete(panel, pair_index - 1):
                left_result = _partial_join_query(panel, pair_index, False, limit, force)
                _fill_table(window.left_table, left_result)
                window.left_info.setText(f"前 {pair_index} 对关联的合并结果")
            else:
                _clear_table(window.left_table)
                window.left_info.setText("前序关联尚未完整")

        # 右侧：选到具体表就立即显示；未选则清空。
        rdb, rtable = _resolve_table(panel, row["table"].currentText() if row.get("table") is not None else "")
        if rdb and rtable:
            right_result = _query_table(panel, rdb, rtable, limit, force)
            _fill_table(window.right_table, right_result)
            window.right_info.setText(_display_table(panel, rdb, rtable))
        else:
            _clear_table(window.right_table)
            window.right_info.setText("未选择右表")

        # 当前对条件未完整时必须清空旧合并结果，不显示历史状态。
        if _chain_complete(panel, pair_index):
            merged = _partial_join_query(panel, pair_index, True, limit, force)
            if merged is not None:
                _fill_table(window.table, merged)
                window.status.setText(f"第 {pair_index + 1} 对关联信息完整，已显示当前合并结果")
                return True
            _clear_table(window.table)
            window.status.setText("当前关联查询失败")
            return False

        _clear_table(window.table)
        window.status.setText("当前关联条件尚未填写完整；本次关联结果为空")
        return False

    def _refresh_data_preview(panel, force=False):
        if not getattr(panel, "_preview_user_opened_v4", False):
            return False
        window = getattr(panel, "_data_preview_v3", None)
        if window is None:
            return False
        if panel._radio_join_v3.isChecked():
            return _refresh_join_preview(panel, force)
        return _refresh_single_preview(panel, force)

    def _schedule_preview(panel, force=False):
        if not getattr(panel, "_preview_user_opened_v4", False):
            return
        QTimer.singleShot(120, lambda: _refresh_data_preview(panel, force))

    def _open_preview(panel):
        panel._preview_user_opened_v4 = True
        window = panel._data_preview_v3
        QDialog.show(window)
        _refresh_data_preview(panel, True)

    def _install_preview_controls(panel):
        button = getattr(panel, "_btn_preview_join_v2", None)
        if button is not None:
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.setText("打开 / 刷新预览")
            button.setToolTip("预览未打开时不自行弹出；打开后自动跟随单表/表关联及当前配置")
            button.clicked.connect(lambda: _open_preview(panel))

        window = getattr(panel, "_data_preview_v3", None)
        if window is not None:
            if hasattr(window, "refresh_button"):
                try:
                    window.refresh_button.clicked.disconnect()
                except TypeError:
                    pass
                window.refresh_button.clicked.connect(lambda: _refresh_data_preview(panel, True))
            if hasattr(window, "pair_combo"):
                try:
                    window.pair_combo.currentIndexChanged.disconnect()
                except TypeError:
                    pass
                window.pair_combo.currentIndexChanged.connect(lambda *_: _refresh_data_preview(panel, False))

    def _refresh_unified(panel):
        _apply_search_behavior(panel)
        _wire_preview_inputs(panel)
        _install_preview_controls(panel)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        _refresh_unified(self)

    def add_join(self, data=None):
        result = previous_add_join(self, data)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    def add_condition(self, row, data=None):
        result = previous_add_condition(self, row, data)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    def add_filter(self):
        result = previous_add_filter(self)
        QTimer.singleShot(0, lambda: _apply_search_behavior(self))
        return result

    def move_join(self, row, delta):
        result = previous_move_join(self, row, delta)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    def remove_join(self, row):
        result = previous_remove_join(self, row)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    def load_binding(self):
        result = previous_load(self)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    def join_changed(self, *args):
        result = previous_join_changed(self, *args)
        _refresh_unified(self)
        _schedule_preview(self)
        return result

    cls.__init__ = panel_init
    cls._add_join_row_v2 = add_join
    cls._add_join_condition_v2 = add_condition
    cls._add_filter_row_v2 = add_filter
    cls._move_join_v2 = move_join
    cls._remove_join_v2 = remove_join
    cls._load_db_binding = load_binding
    cls._on_join_changed_v2 = join_changed
    cls._refresh_data_preview_v7 = _refresh_data_preview

    # 时间字段也改用同一搜索输入规则，取消它自己的 MousePress/FocusIn 立即弹层。
    time_cls = tbp.TimeBindingPanel
    previous_time_init = time_cls.__init__

    def time_init(self, *args, **kwargs):
        previous_time_init(self, *args, **kwargs)
        combo = getattr(self, "_time_field", None)
        if combo is not None:
            old_filter = getattr(self, "_time_field_filter", None)
            if old_filter is not None and combo.lineEdit() is not None:
                try:
                    combo.lineEdit().removeEventFilter(old_filter)
                except RuntimeError:
                    pass
            configure_search_combo(combo)

    time_cls.__init__ = time_init
