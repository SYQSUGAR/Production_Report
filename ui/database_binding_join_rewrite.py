"""用独立 JoinEditorWidget 完全替换旧 V2-V7 JOIN 界面。

旧 JOIN 控件仍保留为隐藏兼容对象，避免历史 monkeypatch 在加载旧模板时访问已删除的
C++ 对象；它们不再进入布局、不再作为查询数据来源。新的 JOIN 编辑器通过结构化数据
与 QueryBinding、返回字段、WHERE、时间字段、SQL 预览和数据案例预览联动。
"""

from __future__ import annotations

from copy import deepcopy


def install_database_binding_join_rewrite():
    import ui.editor_side_panels as esp
    from models.db_config import QueryBinding
    from PyQt6.QtCore import QEvent, QObject, QTimer
    from PyQt6.QtWidgets import QDialog, QTableWidgetItem

    from ui.join_editor_widget import JoinEditorWidget
    from ui.search_combo_behavior import set_search_choices

    if getattr(esp, "_database_binding_join_rewrite_installed", False):
        return
    esp._database_binding_join_rewrite_installed = True

    cls = esp.DatabaseBindingPanel
    previous_init = cls.__init__
    previous_collect = cls._collect_db_binding
    previous_load = cls._load_db_binding
    previous_refresh_metadata = cls.refresh_database_metadata
    previous_update_state = cls._update_db_ui_state

    def _selected_databases(panel):
        return list(getattr(panel._template, "selected_databases", []) or [])

    def _db_type(panel):
        cfg = panel._template.db_configs.get("default") if panel._template else None
        return (getattr(cfg, "db_type", "mysql") or "mysql").lower()

    def _metadata(panel):
        meta = getattr(panel, "_all_db_metadata", None)
        if meta:
            return meta
        editor = getattr(panel, "_editor", None)
        return getattr(editor, "_database_metadata_cache", {}) or {}

    def _current_binding(panel):
        row = getattr(panel, "_current_row", -1)
        col = getattr(panel, "_current_col", -1)
        if row < 0 or col < 0:
            return QueryBinding()
        try:
            cd = panel._template.get_cell_data(row, col)
            return cd.query_binding or QueryBinding()
        except Exception:
            return QueryBinding()

    def _hide_legacy_join(panel):
        group = getattr(panel, "_legacy_join_group_rewrite", None)
        if group is None:
            group = getattr(panel, "_join_group_v2", None)
        if group is None:
            return
        group.hide()
        group.setEnabled(False)
        # 即使旧 V3/V4 的 mode handler 再次 show()，也不会占据任何布局高度。
        group.setMinimumHeight(0)
        group.setMaximumHeight(0)

    def _sync_editor_metadata(panel):
        editor = getattr(panel, "_join_editor_rewrite", None)
        if editor is None:
            return
        editor.set_metadata(_metadata(panel), _selected_databases(panel), _db_type(panel))

    def _resolve_single_table(panel):
        editor = getattr(panel, "_join_editor_rewrite", None)
        if editor is None:
            return "", ""
        return editor.resolve_table(panel._cmb_table.currentText())

    def _single_fields(panel):
        editor = getattr(panel, "_join_editor_rewrite", None)
        if editor is None:
            return [], {}
        db, table = _resolve_single_table(panel)
        columns = editor.columns(db, table) if table else []
        return list(columns), {col: col for col in columns}

    def _active_fields(panel):
        editor = getattr(panel, "_join_editor_rewrite", None)
        if editor is None:
            return [], {}
        if panel._radio_join_v3.isChecked():
            return editor.merged_fields()
        return _single_fields(panel)

    def _sync_time_choices(panel, choices, lookup):
        # 时间面板是独立面板。JOIN 模式传 SQL 可执行字段名，避免保存“字段 (表名)”到 SQL。
        try:
            from ui.time_binding_panel import TimeBindingPanel
            windows = panel.window().findChildren(TimeBindingPanel)
            values = [lookup.get(item, item) for item in choices]
            for time_panel in windows:
                time_panel.set_field_choices(values)
        except Exception:
            pass

    def _update_field_candidates(panel):
        choices, lookup = _active_fields(panel)
        panel._field_display_lookup = dict(lookup)
        panel._merged_field_choices_v3 = list(choices)
        panel._merged_field_sql_v3 = [lookup.get(item, item) for item in choices]

        set_search_choices(panel._cmb_field, choices)
        for fr in list(getattr(panel, "_filter_rows", []) or []):
            combo = fr.get("field_combo")
            if combo is not None:
                set_search_choices(combo, choices)
        _sync_time_choices(panel, choices, lookup)
        return choices, lookup

    def _apply_new_join_to_binding(panel, qb):
        editor = panel._join_editor_rewrite
        selected = _selected_databases(panel)

        if panel._radio_join_v3.isChecked():
            parts = editor.binding_parts()
            qb.database_name = parts["database_name"]
            qb.schema_name = parts["schema_name"]
            qb.table_name = parts["table_name"]
            qb.source_alias = parts["source_alias"]
            qb.joins = parts["joins"]
            qb.qualify_database = len(selected) > 1
            if hasattr(qb, "source_mode"):
                qb.source_mode = "join"
        else:
            db, table = _resolve_single_table(panel)
            qb.database_name = db
            qb.schema_name = ""
            qb.table_name = table
            qb.source_alias = ""
            qb.joins = []
            qb.qualify_database = len(selected) > 1
            if hasattr(qb, "source_mode"):
                qb.source_mode = "single"

        display = panel._cmb_field.currentText().strip()
        lookup = getattr(panel, "_field_display_lookup", {}) or {}
        qb.field_name = lookup.get(display, display)

        # WHERE 仍由旧成熟实现收集，这里只把显示字段翻译成 SQL 字段。
        for item in list(getattr(qb, "filters", []) or []):
            field = str(item.get("field", "") or "")
            if field in lookup:
                item["field"] = lookup[field]

        tb = getattr(qb, "time_binding", None)
        if tb is not None and getattr(tb, "time_field", "") in lookup:
            tb.time_field = lookup[tb.time_field]
        return qb

    def collect_binding(self):
        qb = previous_collect(self)
        if not hasattr(self, "_join_editor_rewrite"):
            return qb
        return _apply_new_join_to_binding(self, qb)

    def _commit(panel):
        if getattr(panel, "_join_rewrite_loading", False):
            return
        _update_field_candidates(panel)
        commit = getattr(panel, "_commit_binding_v2", None)
        if callable(commit):
            commit()
        else:
            try:
                panel._update_sql_preview()
            except Exception:
                pass
        _schedule_preview(panel)

    def _join_changed(panel):
        _hide_legacy_join(panel)
        _commit(panel)

    def _mode_changed(panel):
        editor = getattr(panel, "_join_editor_rewrite", None)
        if editor is None:
            return
        join_mode = panel._radio_join_v3.isChecked()
        editor.setVisible(join_mode)
        _hide_legacy_join(panel)
        _update_field_candidates(panel)
        if not getattr(panel, "_join_rewrite_loading", False):
            commit = getattr(panel, "_commit_binding_v2", None)
            if callable(commit):
                commit()
        _refresh_preview(panel, False)

    # ------------------------------------------------------------------
    # 数据案例预览：只读取新 JoinEditorWidget，不再读取 _join_rows。
    # ------------------------------------------------------------------
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

    def _quote_table(panel, db, table):
        if not table:
            return ""
        if _db_type(panel) == "mysql":
            qdb = db.replace("`", "``")
            qtable = table.replace("`", "``")
            return f"`{qdb}`.`{qtable}`" if db else f"`{qtable}`"
        parts = table.split(".", 1)
        schema, raw = (parts[0], parts[1]) if len(parts) == 2 else ("dbo", table)
        return ".".join(f"[{part.replace(']', ']]')}]" for part in (db, schema, raw) if part)

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
        sql = (
            f"SELECT TOP {limit} * FROM {qualified}"
            if _db_type(panel) == "sqlserver"
            else f"SELECT * FROM {qualified} LIMIT {limit}"
        )
        switch_db = db if len(_selected_databases(panel)) == 1 else ""
        return editor._db_handler.execute_rows(sql, "default", switch_db)

    def _partial_join_query(panel, pair_index, include_current, limit, force=False):
        db_editor, cfg = _ensure_connection(panel, force)
        if db_editor is None:
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
        return db_editor._db_handler.execute_rows(sql, "default", switch_db)

    def _refresh_pair_selector(panel):
        window = getattr(panel, "_data_preview_v3", None)
        editor = getattr(panel, "_join_editor_rewrite", None)
        if window is None or editor is None or not hasattr(window, "pair_combo"):
            return
        current = window.pair_combo.currentIndex()
        window.pair_combo.blockSignals(True)
        window.pair_combo.clear()
        for idx in range(editor.pair_count()):
            window.pair_combo.addItem(editor.pair_label(idx))
        if editor.pair_count():
            window.pair_combo.setCurrentIndex(max(0, min(current, editor.pair_count() - 1)))
        window.pair_combo.blockSignals(False)

    def _refresh_single_preview(panel, force=False):
        window = getattr(panel, "_data_preview_v3", None)
        if window is None:
            return False
        window.setWindowTitle("单表数据预览")
        if hasattr(window, "set_join_mode"):
            window.set_join_mode(False)
        if hasattr(window, "pair_row"):
            window.pair_row.hide()
        if hasattr(window, "pair_splitter"):
            window.pair_splitter.hide()

        db, table = _resolve_single_table(panel)
        if not db or not table:
            _clear_table(window.table)
            window.info.setText("当前数据表：未选择")
            window.status.setText("请选择数据表")
            return False
        limit = int(window.limit.currentText()) if hasattr(window, "limit") else 20
        result = _query_table(panel, db, table, limit, force)
        _fill_table(window.table, result)
        window.info.setText(f"当前数据表：{panel._join_editor_rewrite.display_table(db, table)}")
        window.status.setText("" if result is None else f"显示 {len(result[1])} 行")
        return result is not None

    def _refresh_join_preview(panel, force=False):
        window = getattr(panel, "_data_preview_v3", None)
        editor = getattr(panel, "_join_editor_rewrite", None)
        if window is None or editor is None:
            return False
        window.setWindowTitle("表关联数据预览")
        if hasattr(window, "set_join_mode"):
            window.set_join_mode(True)
        if hasattr(window, "pair_row"):
            window.pair_row.show()
        if hasattr(window, "pair_splitter"):
            window.pair_splitter.show()

        _refresh_pair_selector(panel)
        if editor.pair_count() == 0:
            _clear_table(window.left_table)
            _clear_table(window.right_table)
            _clear_table(window.table)
            window.left_info.setText("未选择左表")
            window.right_info.setText("未选择右表")
            window.info.setText("尚未添加表关联")
            window.status.setText("请添加关联")
            return False

        pair_index = max(0, min(window.pair_combo.currentIndex(), editor.pair_count() - 1))
        card = editor.cards[pair_index]
        limit = int(window.limit.currentText()) if hasattr(window, "limit") else 20
        window.info.setText(f"当前查看第 {pair_index + 1} 对关联；配置到哪，预览到哪")

        if pair_index == 0:
            ldb, ltable = editor.resolve_table(card.left_table.currentText())
            if ldb and ltable:
                _fill_table(window.left_table, _query_table(panel, ldb, ltable, limit, force))
                window.left_info.setText(editor.display_table(ldb, ltable))
            else:
                _clear_table(window.left_table)
                window.left_info.setText("未选择左表")
        elif editor.chain_complete(pair_index - 1):
            _fill_table(window.left_table, _partial_join_query(panel, pair_index, False, limit, force))
            window.left_info.setText(f"前 {pair_index} 对关联的合并结果")
        else:
            _clear_table(window.left_table)
            window.left_info.setText("前序关联尚未完整")

        rdb, rtable = editor.resolve_table(card.right_table.currentText())
        if rdb and rtable:
            _fill_table(window.right_table, _query_table(panel, rdb, rtable, limit, force))
            window.right_info.setText(editor.display_table(rdb, rtable))
        else:
            _clear_table(window.right_table)
            window.right_info.setText("未选择右表")

        if editor.chain_complete(pair_index):
            merged = _partial_join_query(panel, pair_index, True, limit, force)
            _fill_table(window.table, merged)
            window.status.setText(
                f"第 {pair_index + 1} 对关联信息完整，已显示当前合并结果"
                if merged is not None else "当前关联查询失败"
            )
            return merged is not None

        _clear_table(window.table)
        window.status.setText("当前关联条件尚未填写完整；本次关联结果为空")
        return False

    def _refresh_preview(panel, force=False):
        if not getattr(panel, "_join_rewrite_preview_open", False):
            return False
        if panel._radio_join_v3.isChecked():
            return _refresh_join_preview(panel, force)
        return _refresh_single_preview(panel, force)

    def _schedule_preview(panel):
        if getattr(panel, "_join_rewrite_preview_open", False):
            QTimer.singleShot(40, lambda: _refresh_preview(panel, False))

    class _PreviewHideFilter(QObject):
        def __init__(self, panel, window):
            super().__init__(window)
            self.panel = panel

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Hide:
                self.panel._join_rewrite_preview_open = False
            return False

    def _open_preview(panel):
        window = getattr(panel, "_data_preview_v3", None)
        if window is None:
            return
        # 旧 V4/V7 继续认为预览未打开，因此它们的旧 _join_rows 刷新链不会再执行。
        panel._preview_user_opened_v4 = False
        panel._join_rewrite_preview_open = True
        QDialog.show(window)  # 绕过 V4 重写的 show() 状态判断。
        _refresh_preview(panel, True)

    def _install_preview_controls(panel):
        button = getattr(panel, "_btn_preview_join_v2", None)
        if button is not None:
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.setText("打开 / 刷新预览")
            button.setToolTip("预览关闭时不自行弹出；打开后只跟随当前单表/表关联配置")
            button.clicked.connect(lambda: _open_preview(panel))

        window = getattr(panel, "_data_preview_v3", None)
        if window is None:
            return
        panel._preview_user_opened_v4 = False
        panel._join_rewrite_preview_open = False
        filt = _PreviewHideFilter(panel, window)
        window.installEventFilter(filt)
        panel._join_rewrite_preview_filter = filt
        if hasattr(window, "refresh_button"):
            try:
                window.refresh_button.clicked.disconnect()
            except TypeError:
                pass
            window.refresh_button.clicked.connect(lambda: _refresh_preview(panel, True))
        if hasattr(window, "pair_combo"):
            try:
                window.pair_combo.currentIndexChanged.disconnect()
            except TypeError:
                pass
            window.pair_combo.currentIndexChanged.connect(lambda *_: _refresh_preview(panel, False))

    def _install_editor(panel):
        legacy = getattr(panel, "_join_group_v2", None)
        panel._legacy_join_group_rewrite = legacy
        builder = panel._builder_widget.layout()
        insert_at = builder.indexOf(legacy) if legacy is not None else builder.count()

        editor = JoinEditorWidget(panel._builder_widget)
        panel._join_editor_rewrite = editor
        builder.insertWidget(max(0, insert_at), editor)
        if legacy is not None:
            _hide_legacy_join(panel)

        _sync_editor_metadata(panel)
        editor.changed.connect(lambda: _join_changed(panel))
        editor.fieldsChanged.connect(lambda *_: _update_field_candidates(panel))

        # 新组件初始化后再连接，保证它在旧 V3/V7 mode slots 之后收尾。
        panel._radio_single_v3.toggled.connect(lambda *_: _mode_changed(panel))
        panel._radio_join_v3.toggled.connect(lambda *_: _mode_changed(panel))
        panel._cmb_table.currentTextChanged.connect(lambda *_: (_update_field_candidates(panel), _schedule_preview(panel)))
        _install_preview_controls(panel)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        self._join_rewrite_loading = True
        try:
            _install_editor(self)
            qb = _current_binding(self)
            self._join_editor_rewrite.load_binding(qb)
            self._join_editor_rewrite.setVisible(self._radio_join_v3.isChecked())
            _update_field_candidates(self)
            _hide_legacy_join(self)
        finally:
            self._join_rewrite_loading = False

    def load_binding(self):
        self._join_rewrite_loading = True
        try:
            result = previous_load(self)
            _sync_editor_metadata(self)
            qb = _current_binding(self)
            self._join_editor_rewrite.load_binding(qb)
            # 旧模板没有 source_mode 时，已有 joins 就是关联模式。
            mode = getattr(qb, "source_mode", "")
            if mode == "join" or (not mode and list(getattr(qb, "joins", []) or [])):
                self._radio_join_v3.setChecked(True)
            elif mode == "single":
                self._radio_single_v3.setChecked(True)
            self._join_editor_rewrite.setVisible(self._radio_join_v3.isChecked())
            _hide_legacy_join(self)
            _update_field_candidates(self)
        finally:
            self._join_rewrite_loading = False
        _refresh_preview(self, False)
        return result

    def refresh_metadata(self):
        result = previous_refresh_metadata(self)
        _sync_editor_metadata(self)
        _update_field_candidates(self)
        _hide_legacy_join(self)
        _refresh_preview(self, False)
        return result

    def update_state(self):
        result = previous_update_state(self)
        if hasattr(self, "_join_editor_rewrite"):
            self._join_editor_rewrite.setEnabled(self._chk_db_enabled.isChecked())
            self._join_editor_rewrite.setVisible(
                self._chk_db_enabled.isChecked() and self._radio_join_v3.isChecked()
            )
        _hide_legacy_join(self)
        return result

    cls.__init__ = panel_init
    cls._collect_db_binding = collect_binding
    cls._load_db_binding = load_binding
    cls.refresh_database_metadata = refresh_metadata
    cls._update_db_ui_state = update_state
    cls._refresh_data_preview_rewrite = _refresh_preview
