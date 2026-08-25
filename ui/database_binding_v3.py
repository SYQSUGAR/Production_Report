"""数据库绑定 V3：单表/关联流程、左右字段、全局表选择与自动数据预览。"""


def install_database_binding_v3():
    import ui.editor_side_panels as esp
    import ui.workspace_window as ww
    from PyQt6.QtCore import Qt, QEvent, QObject, QTimer
    from PyQt6.QtWidgets import (
        QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
        QHBoxLayout, QLabel, QMessageBox, QPushButton, QRadioButton,
        QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
    )

    if getattr(esp, "_database_binding_v3_installed", False):
        return
    esp._database_binding_v3_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_refresh_metadata = cls.refresh_database_metadata
    previous_load = cls._load_db_binding
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_move_join = cls._move_join_v2
    previous_remove_join = cls._remove_join_v2
    previous_update_state = cls._update_db_ui_state

    class _FullTextToolTipFilter(QObject):
        def __init__(self, line_edit):
            super().__init__(line_edit)
            self.line_edit = line_edit

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.ToolTip:
                text = self.line_edit.text()
                if text:
                    width = self.line_edit.fontMetrics().horizontalAdvance(text)
                    if width > max(1, self.line_edit.contentsRect().width() - 8):
                        QToolTip.showText(event.globalPos(), text, self.line_edit)
                        return True
            return False

    def _enhance_combo(combo):
        if combo is None or not combo.isEditable():
            return
        line = combo.lineEdit()
        if not hasattr(combo, "_v3_tooltip_filter"):
            filt = _FullTextToolTipFilter(line)
            line.installEventFilter(filt)
            combo._v3_tooltip_filter = filt

        if not combo.property("v3_selection_sync"):
            def sync_exact(text, c=combo):
                idx = c.findText(text, Qt.MatchFlag.MatchExactly)
                if idx >= 0 and c.currentIndex() != idx:
                    old = c.blockSignals(True)
                    c.setCurrentIndex(idx)
                    c.setEditText(text)
                    c.blockSignals(old)

            def sync_chosen(text, c=combo):
                text = str(text)
                idx = c.findText(text, Qt.MatchFlag.MatchExactly)
                old = c.blockSignals(True)
                if idx >= 0:
                    c.setCurrentIndex(idx)
                c.setEditText(text)
                c.blockSignals(old)

            line.editingFinished.connect(lambda c=combo: sync_exact(c.currentText(), c))
            combo.activated.connect(lambda *_args, c=combo: sync_exact(c.currentText(), c))
            comp = combo.completer()
            if comp is not None:
                comp.activated.connect(sync_chosen)
            combo.setProperty("v3_selection_sync", True)

    def _set_choices(combo, choices, current=None):
        values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
        text = combo.currentText() if current is None else str(current)
        old = combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        if combo.isEditable():
            combo.setEditText(text)
        elif text in values:
            combo.setCurrentText(text)
        combo.blockSignals(old)
        model = getattr(combo, "_search_model", None)
        if model is not None:
            model.setStringList(values)
        _enhance_combo(combo)

    def _selected_databases(panel):
        return list(getattr(panel._template, "selected_databases", []) or [])

    def _all_tables(panel):
        metadata = getattr(panel, "_all_db_metadata", {}) or {}
        counts = {}
        for db in _selected_databases(panel):
            for table in (metadata.get(db, {}) or {}):
                counts[table] = counts.get(table, 0) + 1
        choices, lookup, reverse = [], {}, {}
        for db in _selected_databases(panel):
            for table in sorted((metadata.get(db, {}) or {}).keys(), key=str.lower):
                display = f"{table} ({db})" if counts.get(table, 0) > 1 else table
                if display in lookup:
                    display = f"{table} ({db})"
                lookup[display] = (db, table)
                reverse[(db, table)] = display
                choices.append(display)
        panel._v3_table_lookup = lookup
        panel._v3_table_reverse = reverse
        return choices

    def _resolve_table(panel, display):
        display = (display or "").strip()
        if not display:
            return "", ""
        lookup = getattr(panel, "_v3_table_lookup", {}) or {}
        if display in lookup:
            return lookup[display]
        # 兼容旧模板/旧输入：唯一表名可以直接反查。
        metadata = getattr(panel, "_all_db_metadata", {}) or {}
        matches = []
        for db in _selected_databases(panel):
            if display in (metadata.get(db, {}) or {}):
                matches.append((db, display))
        return matches[0] if len(matches) == 1 else ("", display)

    def _display_table(panel, database, table):
        return (getattr(panel, "_v3_table_reverse", {}) or {}).get((database, table), table)

    def _columns(panel, database, table):
        return list(((getattr(panel, "_all_db_metadata", {}) or {}).get(database, {}) or {}).get(table, []) or [])

    def _source_ref(panel):
        if getattr(panel, "_radio_join_v3", None) is not None and panel._radio_join_v3.isChecked():
            rows = getattr(panel, "_join_rows", []) or []
            if rows:
                left = rows[0].get("left_table_v3")
                if left is not None:
                    return _resolve_table(panel, left.currentText())
        return _resolve_table(panel, panel._cmb_table.currentText())

    def _row_right_ref(panel, row):
        ref = _resolve_table(panel, row["table"].currentText())
        row["database"].blockSignals(True)
        row["database"].setCurrentText(ref[0])
        row["database"].blockSignals(False)
        row["right_ref_v3"] = ref
        return ref

    def _sources_before(panel, row_index=None):
        source_db, source_table = _source_ref(panel)
        result = []
        if source_table:
            result.append({"database": source_db, "table": source_table, "alias": "t1",
                           "columns": _columns(panel, source_db, source_table)})
        rows = list(getattr(panel, "_join_rows", []) or [])
        limit = len(rows) if row_index is None else row_index
        for idx, row in enumerate(rows[:limit]):
            db, table = _row_right_ref(panel, row)
            if not table:
                continue
            alias = row["alias"].text().strip() or f"t{idx + 2}"
            result.append({"database": db, "table": table, "alias": alias,
                           "columns": _columns(panel, db, table)})
        return result

    def _merged_field_candidates(panel):
        sources = _sources_before(panel, None)
        counts = {}
        table_counts = {}
        for src in sources:
            table_counts[src["table"]] = table_counts.get(src["table"], 0) + 1
            for col in src["columns"]:
                counts[col] = counts.get(col, 0) + 1
        choices, lookup = [], {}
        for src in sources:
            for col in src["columns"]:
                if counts.get(col, 0) == 1:
                    display = col
                else:
                    source = src["table"] if table_counts.get(src["table"], 0) == 1 else f'{src["database"]}.{src["table"]}'
                    display = f"{col} ({source})"
                sql_name = f'{src["alias"]}.{col}' if len(sources) > 1 else col
                if display in lookup:
                    display = f"{col} ({src['database']}.{src['table']})"
                lookup[display] = sql_name
                choices.append(display)
        return choices, lookup

    def _find_label(panel, text):
        for label in panel.findChildren(QLabel):
            if label.text().strip() == text:
                return label
        return None

    def _hide_database_selector(panel):
        combo = getattr(panel, "_cmb_database", None)
        if combo is not None:
            combo.hide()
        label = _find_label(panel, "数据库:")
        if label is not None:
            label.hide()

    def _refresh_global_table_choices(panel, preferred=None):
        choices = _all_tables(panel)
        current = panel._cmb_table.currentText() if preferred is None else preferred
        _set_choices(panel._cmb_table, choices, current)
        for row in getattr(panel, "_join_rows", []) or []:
            left = row.get("left_table_v3")
            if left is not None:
                _set_choices(left, choices)
            _set_choices(row["table"], choices)
            row["database"].hide()
        _refresh_all_join_fields(panel)
        _refresh_merged_fields(panel)

    def _sync_hidden_source(panel):
        database, table = _source_ref(panel)
        if hasattr(panel, "_cmb_database"):
            old = panel._cmb_database.blockSignals(True)
            panel._cmb_database.setCurrentText(database)
            panel._cmb_database.blockSignals(old)
        panel._v3_source_database = database
        panel._v3_source_table = table
        return database, table

    def _decorate_condition(panel, row, cond):
        if cond.get("decorated_v3"):
            return
        cond["decorated_v3"] = True
        layout = cond["widget"].layout()
        cond["op"].setCurrentText("=")
        cond["op"].hide()
        if len(row["conditions"]) == 1:
            cond["connector"].hide()
        else:
            cond["connector"].setEnabled(True)
            cond["connector"].clear()
            cond["connector"].addItems(["AND", "OR"])
            cond["connector"].show()
        # 原控件重新排成：AND/OR | 左 字段 | = | 右 字段 | ×
        layout.removeWidget(cond["left"])
        layout.removeWidget(cond["right"])
        left_label = QLabel("左")
        right_label = QLabel("右")
        equal_label = QLabel("=")
        equal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.insertWidget(1, left_label)
        layout.insertWidget(2, cond["left"], 1)
        layout.insertWidget(3, equal_label)
        layout.insertWidget(4, right_label)
        layout.insertWidget(5, cond["right"], 1)
        cond["left_label_v3"] = left_label
        cond["right_label_v3"] = right_label
        cond["equal_label_v3"] = equal_label
        _enhance_combo(cond["left"]); _enhance_combo(cond["right"])

    def _decorate_join_row(panel, row):
        if not row.get("decorated_v3"):
            row["decorated_v3"] = True
            frame_layout = row["widget"].layout()
            top_layout = frame_layout.itemAt(0).layout()
            row["database"].hide()
            top_layout.removeWidget(row["table"])
            top_layout.removeWidget(row["alias"])

            line = QWidget(row["widget"])
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(0, 0, 0, 0)
            line_layout.setSpacing(4)
            left_label = QLabel("左表:")
            left_table = QComboBox(); left_table.setEditable(True)
            panel._configure_identifier_combo(left_table)
            right_label = QLabel("右表:")
            alias_label = QLabel("别名:")
            line_layout.addWidget(left_label)
            line_layout.addWidget(left_table, 1)
            line_layout.addWidget(right_label)
            line_layout.addWidget(row["table"], 1)
            line_layout.addWidget(alias_label)
            line_layout.addWidget(row["alias"])
            frame_layout.insertWidget(1, line)
            row["table_line_v3"] = line
            row["left_label_v3"] = left_label
            row["left_table_v3"] = left_table
            row["right_label_v3"] = right_label
            row["alias_label_v3"] = alias_label
            _enhance_combo(left_table); _enhance_combo(row["table"])
            left_table.activated.connect(lambda *_args, r=row: _on_left_table_changed(panel, r))
            left_table.lineEdit().editingFinished.connect(lambda r=row: _on_left_table_changed(panel, r))
            row["table"].activated.connect(lambda *_args, r=row: _on_right_table_changed(panel, r))
            row["table"].lineEdit().editingFinished.connect(lambda r=row: _on_right_table_changed(panel, r))

        choices = _all_tables(panel)
        _set_choices(row["left_table_v3"], choices)
        _set_choices(row["table"], choices)
        row["database"].hide()
        for cond in row["conditions"]:
            _decorate_condition(panel, row, cond)

    def _layout_join_rows(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        choices = _all_tables(panel)
        for idx, row in enumerate(rows):
            _decorate_join_row(panel, row)
            row["number"].setText(f"{idx + 1}.")
            row["up"].setEnabled(idx > 0)
            row["down"].setEnabled(idx < len(rows) - 1)
            left = row["left_table_v3"]
            if idx == 0:
                row["left_label_v3"].setText("左表:")
                row["right_label_v3"].setText("右表:")
                row["left_label_v3"].show(); left.show()
                if not left.currentText().strip():
                    current = panel._cmb_table.currentText().strip()
                    _set_choices(left, choices, current)
            else:
                row["left_label_v3"].setText("当前合并结果")
                row["left_label_v3"].show(); left.hide()
                row["right_label_v3"].setText("关联表:")
            for cidx, cond in enumerate(row["conditions"]):
                _decorate_condition(panel, row, cond)
                if cidx == 0:
                    cond["connector"].hide()
                else:
                    cond["connector"].show()
        if hasattr(panel, "_join_group_v2"):
            panel._join_group_v2.setTitle(f"表关联 JOIN（{len(rows)}）")
        _sync_hidden_source(panel)

    def _refresh_join_fields(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return
        idx = rows.index(row)
        left_sources = _sources_before(panel, idx)
        left_choices = []
        left_lookup = {}
        for src in left_sources:
            for col in src["columns"]:
                if col not in left_lookup:
                    left_choices.append(col)
                    left_lookup[col] = f'{src["alias"]}.{col}'
        right_db, right_table = _row_right_ref(panel, row)
        alias = row["alias"].text().strip() or f"t{idx + 2}"
        right_choices = _columns(panel, right_db, right_table)
        right_lookup = {col: f"{alias}.{col}" for col in right_choices}
        row["left_field_lookup_v3"] = left_lookup
        row["right_field_lookup_v3"] = right_lookup
        for cond in row["conditions"]:
            _set_choices(cond["left"], left_choices)
            _set_choices(cond["right"], right_choices)

    def _refresh_all_join_fields(panel):
        _layout_join_rows(panel)
        for row in list(getattr(panel, "_join_rows", []) or []):
            _refresh_join_fields(panel, row)

    def _refresh_merged_fields(panel):
        choices, lookup = _merged_field_candidates(panel)
        panel._field_display_lookup = lookup
        _set_choices(panel._cmb_field, choices)
        for fr in getattr(panel, "_filter_rows", []) or []:
            _set_choices(fr["field_combo"], choices)
        # 时间字段由 WorkspaceWindow 继续同步；这里保留来源信息供其读取。
        panel._v3_merged_field_choices = choices
        panel._v3_merged_field_lookup = lookup

    def _on_left_table_changed(panel, row):
        if not getattr(panel, "_join_rows", None) or row is not panel._join_rows[0]:
            return
        _sync_hidden_source(panel)
        _refresh_all_join_fields(panel)
        _refresh_merged_fields(panel)
        _commit_v3(panel)
        _auto_preview(panel)

    def _on_right_table_changed(panel, row):
        _row_right_ref(panel, row)
        _refresh_all_join_fields(panel)
        _refresh_merged_fields(panel)
        _commit_v3(panel)
        _auto_preview(panel)

    def _collect_joins(panel):
        result = []
        rows = list(getattr(panel, "_join_rows", []) or [])
        for idx, row in enumerate(rows):
            db, table = _row_right_ref(panel, row)
            conditions = []
            left_lookup = row.get("left_field_lookup_v3", {})
            right_lookup = row.get("right_field_lookup_v3", {})
            for cidx, cond in enumerate(row["conditions"]):
                left_text = cond["left"].currentText().strip()
                right_text = cond["right"].currentText().strip()
                if not left_text and not right_text:
                    continue
                conditions.append({
                    "connector": "AND" if cidx == 0 else cond["connector"].currentText().upper(),
                    "left": left_lookup.get(left_text, left_text),
                    "op": "=",
                    "right": right_lookup.get(right_text, right_text),
                })
            result.append({
                "type": row["type"].currentText(),
                "database_name": db,
                "schema_name": "",
                "table_name": table,
                "alias": row["alias"].text().strip() or f"t{idx + 2}",
                "conditions": conditions,
            })
        return result

    def _collect_binding(panel):
        # 从现有控件先收集通用项，再覆盖 V3 的表/字段/JOIN 身份。
        qb = panel._v2_collect_for_v3()
        join_mode = panel._radio_join_v3.isChecked()
        database, table = _source_ref(panel)
        joins = _collect_joins(panel) if join_mode else []
        qb.database_name = database
        qb.schema_name = ""
        qb.table_name = table
        qb.qualify_database = len(_selected_databases(panel)) > 1
        qb.source_alias = "t1" if joins else ""
        qb.joins = joins
        field_text = panel._cmb_field.currentText().strip()
        qb.field_name = (getattr(panel, "_field_display_lookup", {}) or {}).get(field_text, field_text)
        filters = []
        for index, fr in enumerate(getattr(panel, "_filter_rows", []) or []):
            ftext = fr["field_combo"].currentText().strip()
            value = fr["value"].text().strip()
            if not ftext and not value:
                continue
            filters.append({
                "connector": "where" if index == 0 else fr["connector"].currentText(),
                "field": (getattr(panel, "_field_display_lookup", {}) or {}).get(ftext, ftext),
                "op": panel._v3_sql_operators[fr["op"].currentIndex()],
                "value": value,
            })
        qb.filters = filters
        return qb

    def _commit_v3(panel, *_args):
        if getattr(panel, "_suppress_update", False) or getattr(panel, "_v2_loading", False):
            return
        qb = _collect_binding(panel)
        panel._apply_db_patch({
            "enabled": qb.enabled, "query_type": qb.query_type, "db_config_key": qb.db_config_key,
            "database_name": qb.database_name, "schema_name": qb.schema_name,
            "qualify_database": qb.qualify_database, "table_name": qb.table_name,
            "source_alias": qb.source_alias, "field_name": qb.field_name,
            "aggregate_func": qb.aggregate_func, "sql_mode": qb.sql_mode,
            "custom_sql": qb.custom_sql, "sync_modes": qb.sync_modes,
            "joins": qb.joins, "filters": qb.filters, "date_placeholder": qb.date_placeholder,
        })
        if hasattr(panel, "_refresh_filter_title_v2"):
            panel._refresh_filter_title_v2()

    def _join_complete(panel):
        if not panel._radio_join_v3.isChecked():
            return False
        qb = _collect_binding(panel)
        if not qb.table_name or not qb.joins:
            return False
        if qb.validate_joins():
            return False
        return all((j.get("table_name") or "").strip() and (j.get("conditions") or []) for j in qb.joins)

    def _quote_table(panel, database, table):
        cfg = panel._template.db_configs.get("default")
        db_type = (getattr(cfg, "db_type", "mysql") or "mysql").lower()
        if db_type == "mysql":
            safe_db = database.replace("`", "``")
            safe_table = table.replace("`", "``")
            return f"`{safe_db}`.`{safe_table}`" if database else f"`{safe_table}`"
        parts = table.split(".", 1)
        if len(parts) == 2:
            schema, raw = parts
        else:
            schema, raw = "dbo", table
        return ".".join(f"[{p.replace(']', ']]')}]" for p in (database, schema, raw) if p)

    class _PreviewWindow(QDialog):
        def __init__(self, panel):
            super().__init__(panel.window())
            self.panel = panel
            self.setWindowTitle("数据预览")
            self.resize(1180, 650)
            self.setModal(False)
            root = QVBoxLayout(self)
            self.info = QLabel("尚未选择数据表")
            self.info.setWordWrap(True)
            root.addWidget(self.info)
            tools = QHBoxLayout()
            tools.addWidget(QLabel("显示行数:"))
            self.limit = QComboBox(); self.limit.addItems(["10", "20", "50", "100"]); self.limit.setCurrentText("20")
            self.refresh_button = QPushButton("刷新")
            self.refresh_button.clicked.connect(lambda: _refresh_preview(self.panel, force=True))
            tools.addWidget(self.limit); tools.addWidget(self.refresh_button); tools.addStretch(1)
            root.addLayout(tools)
            self.table = QTableWidget()
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setAlternatingRowColors(True)
            root.addWidget(self.table, 1)
            self.status = QLabel("")
            self.status.setStyleSheet("color:#666;")
            root.addWidget(self.status)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.hide)
            root.addWidget(buttons)

        def closeEvent(self, event):
            event.ignore()
            self.hide()

    def _preview_window(panel):
        window = getattr(panel, "_preview_window_v3", None)
        if window is None:
            window = _PreviewWindow(panel)
            panel._preview_window_v3 = window
        return window

    def _preview_headers(panel, qb, raw):
        if not qb.joins:
            return list(raw)
        sources = _sources_before(panel, None)
        expected = []
        counts = {}
        table_counts = {}
        for src in sources:
            table_counts[src["table"]] = table_counts.get(src["table"], 0) + 1
            for col in src["columns"]:
                counts[col] = counts.get(col, 0) + 1
                expected.append((col, src))
        if len(expected) != len(raw):
            return list(raw)
        result = []
        for col, src in expected:
            if counts.get(col, 0) == 1:
                result.append(col)
            else:
                source = src["table"] if table_counts.get(src["table"], 0) == 1 else f'{src["database"]}.{src["table"]}'
                result.append(f"{col} ({source})")
        return result

    def _refresh_preview(panel, force=False):
        editor = getattr(panel, "_editor", None)
        if editor is None:
            return False
        cfg = editor._template.db_configs.get("default")
        if cfg is None:
            return False
        join_mode = panel._radio_join_v3.isChecked()
        qb = _collect_binding(panel)
        if join_mode:
            if not _join_complete(panel):
                # 关联还没填完整时保留上一份有效预览，不清空、不报错。
                return False
            sql = qb.build_join_preview_sql(int(_preview_window(panel).limit.currentText()), cfg.db_type)
            description = "合并结果：" + " + ".join([qb.table_name] + [j.get("table_name", "") for j in qb.joins])
            db_for_query = qb.database_name if len(_selected_databases(panel)) == 1 else ""
        else:
            database, table = _source_ref(panel)
            if not database or not table:
                return False
            limit = int(_preview_window(panel).limit.currentText())
            qualified = _quote_table(panel, database, table)
            if (getattr(cfg, "db_type", "mysql") or "mysql").lower() == "sqlserver":
                sql = f"SELECT TOP {limit} * FROM {qualified}"
            else:
                sql = f"SELECT * FROM {qualified} LIMIT {limit}"
            description = f"数据表：{_display_table(panel, database, table)}"
            db_for_query = database if len(_selected_databases(panel)) == 1 else ""

        if not editor._db_handler.is_connected("default") and not editor._db_handler.connect(cfg, "default"):
            if force:
                QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "数据库连接失败")
            return False
        result = editor._db_handler.execute_rows(sql, "default", db_for_query)
        if result is None:
            if force:
                QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "查询失败")
            return False
        raw, rows = result
        window = _preview_window(panel)
        headers = _preview_headers(panel, qb, raw)
        window.table.clear()
        window.table.setColumnCount(len(headers))
        window.table.setHorizontalHeaderLabels(headers)
        window.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                window.table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        window.table.resizeColumnsToContents()
        window.info.setText(description)
        if join_mode:
            window.status.setText(f"显示 {len(rows)} 行 | JOIN 配置完整后自动更新 | 不应用 WHERE、时间条件或聚合")
        else:
            window.status.setText(f"显示 {len(rows)} 行 | 选择数据表后自动更新")
        window.show(); window.raise_(); window.activateWindow()
        panel._last_valid_preview_sql_v3 = sql
        return True

    def _auto_preview(panel):
        if getattr(panel, "_v2_loading", False):
            return
        if panel._radio_join_v3.isChecked() and not _join_complete(panel):
            return
        QTimer.singleShot(120, lambda: _refresh_preview(panel, force=False))

    def _on_single_table(panel):
        if panel._radio_join_v3.isChecked():
            return
        _sync_hidden_source(panel)
        _refresh_merged_fields(panel)
        _commit_v3(panel)
        _auto_preview(panel)

    def _set_mode(panel, join_mode):
        panel._radio_join_v3.blockSignals(True); panel._radio_single_v3.blockSignals(True)
        panel._radio_join_v3.setChecked(join_mode); panel._radio_single_v3.setChecked(not join_mode)
        panel._radio_join_v3.blockSignals(False); panel._radio_single_v3.blockSignals(False)
        table_label = getattr(panel, "_table_label_v3", None)
        panel._cmb_table.setVisible(not join_mode)
        if table_label is not None:
            table_label.setVisible(not join_mode)
        panel._join_group_v2.setVisible(join_mode)
        if join_mode and not getattr(panel, "_join_rows", []):
            panel._add_join_row_v2()
        _layout_join_rows(panel)
        _refresh_all_join_fields(panel)
        _refresh_merged_fields(panel)
        _commit_v3(panel)
        _auto_preview(panel)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        from models.db_config import SQL_OPERATORS
        self._v3_sql_operators = SQL_OPERATORS
        # V2 收集器留作通用配置字段的兼容来源。
        self._v2_collect_for_v3 = self._collect_db_binding

        _hide_database_selector(self)
        _all_tables(self)

        self._table_label_v3 = _find_label(self, "数据表:")
        old_field_label = _find_label(self, "字段:")
        if old_field_label is not None:
            old_field_label.hide()

        builder = self._builder_widget.layout()
        mode_box = QGroupBox("数据来源")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(6, 5, 6, 5)
        self._radio_single_v3 = QRadioButton("单表")
        self._radio_join_v3 = QRadioButton("表关联")
        self._radio_single_v3.setChecked(True)
        mode_layout.addWidget(self._radio_single_v3); mode_layout.addWidget(self._radio_join_v3); mode_layout.addStretch(1)
        builder.insertWidget(1, mode_box)

        # 返回字段统一放在 JOIN 后。单表模式下 JOIN 隐藏，因此仍紧随数据表。
        return_row = QWidget()
        return_layout = QHBoxLayout(return_row)
        return_layout.setContentsMargins(0, 0, 0, 0)
        return_layout.addWidget(QLabel("返回字段:"))
        return_layout.addWidget(self._cmb_field, 1)
        join_idx = builder.indexOf(self._join_group_v2)
        builder.insertWidget(join_idx + 1 if join_idx >= 0 else builder.count(), return_row)
        self._return_row_v3 = return_row

        # 数据预览入口移到数据来源上方/附近，不再放在 SQL 预览底部。
        old_parent_layout = self._btn_preview_join_v2.parentWidget().layout()
        if old_parent_layout is not None:
            old_parent_layout.removeWidget(self._btn_preview_join_v2)
        preview_row = QWidget()
        preview_layout = QHBoxLayout(preview_row)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("数据案例预览:"))
        self._btn_preview_join_v2.setText("打开 / 刷新预览")
        self._btn_preview_join_v2.setToolTip("单表选择后自动刷新；关联配置完整后自动刷新；不完整时保留上一份有效结果")
        preview_layout.addWidget(self._btn_preview_join_v2)
        preview_layout.addStretch(1)
        builder.insertWidget(2, preview_row)
        self._preview_row_v3 = preview_row

        try:
            self._btn_preview_join_v2.clicked.disconnect()
        except TypeError:
            pass
        self._btn_preview_join_v2.clicked.connect(lambda: _refresh_preview(self, force=True))

        self._radio_single_v3.toggled.connect(lambda checked: checked and _set_mode(self, False))
        self._radio_join_v3.toggled.connect(lambda checked: checked and _set_mode(self, True))
        _enhance_combo(self._cmb_table); _enhance_combo(self._cmb_field)
        self._cmb_table.activated.connect(lambda *_: _on_single_table(self))
        self._cmb_table.lineEdit().editingFinished.connect(lambda: _on_single_table(self))
        _refresh_global_table_choices(self)
        _set_mode(self, False)

    def refresh_metadata(self):
        result = previous_refresh_metadata(self)
        _hide_database_selector(self)
        _refresh_global_table_choices(self)
        return result

    def add_condition(self, join_row, data=None):
        result = previous_add_condition(self, join_row, data)
        if join_row.get("conditions"):
            _decorate_condition(self, join_row, join_row["conditions"][-1])
        _refresh_join_fields(self, join_row)
        return result

    def add_join(self, data=None):
        result = previous_add_join(self, data)
        if self._join_rows:
            row = self._join_rows[-1]
            _decorate_join_row(self, row)
            if data and len(self._join_rows) == 1:
                db = getattr(self, "_v3_source_database", "") or data.get("source_database", "")
                table = getattr(self, "_v3_source_table", "") or self._cmb_table.currentText().strip()
                row["left_table_v3"].setCurrentText(_display_table(self, db, table))
        _layout_join_rows(self)
        _refresh_all_join_fields(self)
        _refresh_merged_fields(self)
        return result

    def move_join(self, row, delta):
        result = previous_move_join(self, row, delta)
        _layout_join_rows(self); _refresh_all_join_fields(self); _refresh_merged_fields(self)
        _commit_v3(self); _auto_preview(self)
        return result

    def remove_join(self, row):
        result = previous_remove_join(self, row)
        _layout_join_rows(self); _refresh_all_join_fields(self); _refresh_merged_fields(self)
        _commit_v3(self); _auto_preview(self)
        return result

    def load_binding(self):
        result = previous_load(self)
        if self._current_row < 0 or self._current_col < 0:
            return result
        qb = self._template.get_cell_data(self._current_row, self._current_col).query_binding
        _refresh_global_table_choices(self)
        if qb is None:
            _set_mode(self, False)
            return result
        join_mode = bool(qb.joins)
        if qb.database_name and qb.table_name:
            display = _display_table(self, qb.database_name, qb.table_name)
            self._cmb_table.blockSignals(True); self._cmb_table.setCurrentText(display); self._cmb_table.blockSignals(False)
        _set_mode(self, join_mode)
        if join_mode and self._join_rows:
            first = self._join_rows[0]
            first["left_table_v3"].blockSignals(True)
            first["left_table_v3"].setCurrentText(_display_table(self, qb.database_name, qb.table_name))
            first["left_table_v3"].blockSignals(False)
        _layout_join_rows(self); _refresh_all_join_fields(self); _refresh_merged_fields(self)
        display_field = qb.field_name
        for display, sql_name in (getattr(self, "_field_display_lookup", {}) or {}).items():
            if sql_name == qb.field_name:
                display_field = display; break
        self._cmb_field.blockSignals(True); self._cmb_field.setCurrentText(display_field); self._cmb_field.blockSignals(False)
        return result

    def update_state(self):
        result = previous_update_state(self)
        enabled = self._chk_db_enabled.isChecked()
        if hasattr(self, "_preview_row_v3"):
            self._preview_row_v3.setEnabled(enabled)
        return result

    def on_join_changed(self, *_args):
        if getattr(self, "_suppress_update", False) or getattr(self, "_v2_loading", False):
            return
        _layout_join_rows(self)
        _refresh_all_join_fields(self)
        _refresh_merged_fields(self)
        _commit_v3(self)
        _auto_preview(self)

    def refresh_identifier_choices(self, *_args):
        _refresh_all_join_fields(self)
        _refresh_merged_fields(self)

    # 替换/增强 V2 行为。
    cls.__init__ = panel_init
    cls.refresh_database_metadata = refresh_metadata
    cls._add_join_condition_v2 = add_condition
    cls._add_join_row_v2 = add_join
    cls._move_join_v2 = move_join
    cls._remove_join_v2 = remove_join
    cls._load_db_binding = load_binding
    cls._update_db_ui_state = update_state
    cls._on_join_changed_v2 = on_join_changed
    cls._refresh_identifier_choices = refresh_identifier_choices
    cls._refresh_identifier_choices_v2 = refresh_identifier_choices
    cls._collect_db_binding = _collect_binding
    cls._collect_binding_v2 = _collect_binding
    cls._commit_binding_v2 = _commit_v3
    cls._on_db_config_changed = _commit_v3
    cls._preview_join_result_v2 = lambda self: _refresh_preview(self, force=True)
    cls._refresh_preview_v3 = lambda self, force=False: _refresh_preview(self, force)

    # 工作区右侧默认加宽，仍保留可折叠与可调整行为。
    previous_workspace_init = ww.WorkspaceWindow.__init__

    def workspace_init(self, *args, **kwargs):
        previous_workspace_init(self, *args, **kwargs)
        right = getattr(self, "_right_panel_container", None)
        if right is not None:
            right.setMinimumWidth(500)
            right.setMaximumWidth(760)
        splitter = getattr(self, "_main_splitter", None)
        if splitter is not None:
            splitter.setSizes([320, 880, 560])
            try:
                splitter.configure_side("right", panel_index=2, expanded_width=560)
            except Exception:
                pass

    ww.WorkspaceWindow.__init__ = workspace_init
