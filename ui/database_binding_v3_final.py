"""数据库绑定最终交互：单表/关联、左右等值 JOIN、全局表候选、自动数据预览。"""


def install_database_binding_v3_final():
    import ui.editor_side_panels as esp
    import ui.workspace_window as ww
    from models.db_config import SQL_OPERATORS
    from PyQt6.QtCore import Qt, QEvent, QObject, QTimer
    from PyQt6.QtWidgets import (
        QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
        QHBoxLayout, QLabel, QMessageBox, QPushButton, QRadioButton,
        QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
    )

    if getattr(esp, "_database_binding_v3_final_installed", False):
        return
    esp._database_binding_v3_final_installed = True
    cls = esp.DatabaseBindingPanel

    # 这些都是 V2/finish 已经安装好的实现；最终版只在其上调整交互。
    previous_init = cls.__init__
    previous_collect = cls._collect_db_binding
    previous_refresh_metadata = cls.refresh_database_metadata
    previous_load = cls._load_db_binding
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_move_join = cls._move_join_v2
    previous_remove_join = cls._remove_join_v2
    previous_update_state = cls._update_db_ui_state
    previous_workspace_init = ww.WorkspaceWindow.__init__

    class _FullTextTip(QObject):
        def __init__(self, edit):
            super().__init__(edit)
            self.edit = edit

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.ToolTip:
                text = self.edit.text()
                if text and self.edit.fontMetrics().horizontalAdvance(text) > self.edit.contentsRect().width() - 8:
                    QToolTip.showText(event.globalPos(), text, self.edit)
                    return True
            return False

    def _enhance_combo(combo):
        if combo is None or not combo.isEditable():
            return
        edit = combo.lineEdit()
        if not hasattr(combo, "_v3_final_tip"):
            filt = _FullTextTip(edit)
            edit.installEventFilter(filt)
            combo._v3_final_tip = filt
        if combo.property("v3_final_sync"):
            return

        def sync_exact(c=combo):
            text = c.currentText()
            idx = c.findText(text, Qt.MatchFlag.MatchExactly)
            if idx >= 0 and c.currentIndex() != idx:
                old = c.blockSignals(True)
                c.setCurrentIndex(idx)
                c.setEditText(text)
                c.blockSignals(old)

        edit.editingFinished.connect(sync_exact)
        combo.activated.connect(lambda *_: sync_exact())
        comp = combo.completer()
        if comp is not None:
            def chosen(text, c=combo):
                text = str(text)
                idx = c.findText(text, Qt.MatchFlag.MatchExactly)
                old = c.blockSignals(True)
                if idx >= 0:
                    c.setCurrentIndex(idx)
                c.setEditText(text)
                c.blockSignals(old)
            comp.activated.connect(chosen)
        combo.setProperty("v3_final_sync", True)

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

    def _selected(panel):
        return list(getattr(panel._template, "selected_databases", []) or [])

    def _build_table_lookup(panel):
        meta = getattr(panel, "_all_db_metadata", {}) or {}
        counts = {}
        for db in _selected(panel):
            for table in (meta.get(db, {}) or {}):
                counts[table] = counts.get(table, 0) + 1
        choices, lookup, reverse = [], {}, {}
        for db in _selected(panel):
            for table in sorted((meta.get(db, {}) or {}).keys(), key=str.lower):
                display = f"{table} ({db})" if counts.get(table, 0) > 1 else table
                lookup[display] = (db, table)
                reverse[(db, table)] = display
                choices.append(display)
        panel._table_lookup_v3 = lookup
        panel._table_reverse_v3 = reverse
        return choices

    def _resolve_table(panel, text):
        text = (text or "").strip()
        if not text:
            return "", ""
        lookup = getattr(panel, "_table_lookup_v3", {}) or {}
        if text in lookup:
            return lookup[text]
        meta = getattr(panel, "_all_db_metadata", {}) or {}
        matches = [(db, text) for db in _selected(panel) if text in (meta.get(db, {}) or {})]
        return matches[0] if len(matches) == 1 else ("", text)

    def _display_table(panel, db, table):
        return (getattr(panel, "_table_reverse_v3", {}) or {}).get((db, table), table)

    def _columns(panel, db, table):
        return list(((getattr(panel, "_all_db_metadata", {}) or {}).get(db, {}) or {}).get(table, []) or [])

    def _source_ref(panel):
        if hasattr(panel, "_radio_join_v3") and panel._radio_join_v3.isChecked() and getattr(panel, "_join_rows", []):
            left = panel._join_rows[0].get("left_table_v3")
            if left is not None:
                return _resolve_table(panel, left.currentText())
        return _resolve_table(panel, panel._cmb_table.currentText())

    def _right_ref(panel, row):
        db, table = _resolve_table(panel, row["table"].currentText())
        row["database"].blockSignals(True)
        row["database"].setCurrentText(db)
        row["database"].blockSignals(False)
        return db, table

    def _sources(panel, before_index=None):
        db, table = _source_ref(panel)
        result = []
        if table:
            result.append({"db": db, "table": table, "alias": "t1", "columns": _columns(panel, db, table)})
        rows = list(getattr(panel, "_join_rows", []) or [])
        stop = len(rows) if before_index is None else before_index
        for idx, row in enumerate(rows[:stop]):
            rdb, rtable = _right_ref(panel, row)
            if rtable:
                result.append({
                    "db": rdb, "table": rtable,
                    "alias": row["alias"].text().strip() or f"t{idx + 2}",
                    "columns": _columns(panel, rdb, rtable),
                })
        return result

    def _merged_fields(panel):
        sources = _sources(panel)
        counts, table_counts = {}, {}
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
                    source = src["table"] if table_counts.get(src["table"], 0) == 1 else f'{src["db"]}.{src["table"]}'
                    display = f"{col} ({source})"
                lookup[display] = f'{src["alias"]}.{col}' if len(sources) > 1 else col
                choices.append(display)
        return choices, lookup

    def _find_label(panel, text):
        for label in panel.findChildren(QLabel):
            if label.text().strip() == text:
                return label
        return None

    def _hide_database(panel):
        combo = getattr(panel, "_cmb_database", None)
        if combo is not None:
            combo.hide()
        label = _find_label(panel, "数据库:")
        if label is not None:
            label.hide()

    def _sync_hidden_source(panel):
        db, table = _source_ref(panel)
        if hasattr(panel, "_cmb_database"):
            old = panel._cmb_database.blockSignals(True)
            panel._cmb_database.setCurrentText(db)
            panel._cmb_database.blockSignals(old)
        panel._source_db_v3 = db
        panel._source_table_v3 = table
        return db, table

    def _refresh_table_choices(panel):
        choices = _build_table_lookup(panel)
        _set_choices(panel._cmb_table, choices)
        for row in getattr(panel, "_join_rows", []) or []:
            if row.get("left_table_v3") is not None:
                _set_choices(row["left_table_v3"], choices)
            _set_choices(row["table"], choices)
            row["database"].hide()

    def _decorate_condition(panel, row, cond):
        if cond.get("v3_decorated"):
            return
        cond["v3_decorated"] = True
        layout = cond["widget"].layout()
        cond["op"].setCurrentText("=")
        cond["op"].hide()
        layout.removeWidget(cond["left"])
        layout.removeWidget(cond["right"])
        left_label = QLabel("左")
        equal_label = QLabel("=")
        right_label = QLabel("右")
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

    def _decorate_row(panel, row):
        if not row.get("v3_decorated"):
            row["v3_decorated"] = True
            frame_layout = row["widget"].layout()
            top = frame_layout.itemAt(0).layout()
            row["database"].hide()
            top.removeWidget(row["table"])
            top.removeWidget(row["alias"])

            table_line = QWidget(row["widget"])
            tl = QHBoxLayout(table_line)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(4)
            left_label = QLabel("左表:")
            left_table = QComboBox(); left_table.setEditable(True)
            panel._configure_identifier_combo(left_table)
            right_label = QLabel("右表:")
            alias_label = QLabel("别名:")
            tl.addWidget(left_label)
            tl.addWidget(left_table, 1)
            tl.addWidget(right_label)
            tl.addWidget(row["table"], 1)
            tl.addWidget(alias_label)
            tl.addWidget(row["alias"])
            frame_layout.insertWidget(1, table_line)
            row["table_line_v3"] = table_line
            row["left_label_v3"] = left_label
            row["left_table_v3"] = left_table
            row["right_label_v3"] = right_label
            row["alias_label_v3"] = alias_label
            _enhance_combo(left_table); _enhance_combo(row["table"])
            left_table.activated.connect(lambda *_args, r=row: _left_table_changed(panel, r))
            left_table.lineEdit().editingFinished.connect(lambda r=row: _left_table_changed(panel, r))
            row["table"].activated.connect(lambda *_args, r=row: _right_table_changed(panel, r))
            row["table"].lineEdit().editingFinished.connect(lambda r=row: _right_table_changed(panel, r))
        for cond in row["conditions"]:
            _decorate_condition(panel, row, cond)

    def _layout_rows(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        choices = _build_table_lookup(panel)
        for idx, row in enumerate(rows):
            _decorate_row(panel, row)
            _set_choices(row["table"], choices)
            _set_choices(row["left_table_v3"], choices)
            row["number"].setText(f"{idx + 1}.")
            row["up"].setEnabled(idx > 0)
            row["down"].setEnabled(idx < len(rows) - 1)
            if idx == 0:
                row["left_label_v3"].setText("左表:")
                row["left_table_v3"].show()
                row["right_label_v3"].setText("右表:")
                if not row["left_table_v3"].currentText().strip():
                    row["left_table_v3"].setCurrentText(panel._cmb_table.currentText())
            else:
                row["left_label_v3"].setText("当前合并结果")
                row["left_table_v3"].hide()
                row["right_label_v3"].setText("关联表:")
            for cidx, cond in enumerate(row["conditions"]):
                _decorate_condition(panel, row, cond)
                if cidx == 0:
                    cond["connector"].hide()
                else:
                    cond["connector"].setEnabled(True)
                    if cond["connector"].count() != 2:
                        current = cond["connector"].currentText() or "AND"
                        cond["connector"].blockSignals(True)
                        cond["connector"].clear(); cond["connector"].addItems(["AND", "OR"])
                        cond["connector"].setCurrentText(current)
                        cond["connector"].blockSignals(False)
                    cond["connector"].show()
        if hasattr(panel, "_join_group_v2"):
            panel._join_group_v2.setTitle(f"表关联 JOIN（{len(rows)}）")
        _sync_hidden_source(panel)

    def _refresh_join_fields(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return
        idx = rows.index(row)
        left_sources = _sources(panel, idx)
        left_choices, left_lookup = [], {}
        for src in left_sources:
            for col in src["columns"]:
                if col not in left_lookup:
                    # JOIN 输入框只显示字段名；重复字段按当前合并顺序取第一个来源。
                    left_choices.append(col)
                    left_lookup[col] = f'{src["alias"]}.{col}'
        db, table = _right_ref(panel, row)
        alias = row["alias"].text().strip() or f"t{idx + 2}"
        right_choices = _columns(panel, db, table)
        right_lookup = {col: f"{alias}.{col}" for col in right_choices}
        row["left_lookup_v3"] = left_lookup
        row["right_lookup_v3"] = right_lookup
        for cond in row["conditions"]:
            _set_choices(cond["left"], left_choices)
            _set_choices(cond["right"], right_choices)

    def _refresh_fields(panel):
        _layout_rows(panel)
        for row in getattr(panel, "_join_rows", []) or []:
            _refresh_join_fields(panel, row)
        choices, lookup = _merged_fields(panel)
        panel._field_display_lookup = lookup
        panel._merged_field_choices_v3 = choices
        panel._merged_field_sql_v3 = list(lookup.values())
        _set_choices(panel._cmb_field, choices)
        for fr in getattr(panel, "_filter_rows", []) or []:
            _set_choices(fr["field_combo"], choices)

    def _collect_joins(panel):
        joins = []
        for idx, row in enumerate(getattr(panel, "_join_rows", []) or []):
            db, table = _right_ref(panel, row)
            conditions = []
            for cidx, cond in enumerate(row["conditions"]):
                left_text = cond["left"].currentText().strip()
                right_text = cond["right"].currentText().strip()
                if not left_text and not right_text:
                    continue
                conditions.append({
                    "connector": "AND" if cidx == 0 else cond["connector"].currentText().upper(),
                    "left": row.get("left_lookup_v3", {}).get(left_text, left_text),
                    "op": "=",
                    "right": row.get("right_lookup_v3", {}).get(right_text, right_text),
                })
            joins.append({
                "type": row["type"].currentText(),
                "database_name": db,
                "schema_name": "",
                "table_name": table,
                "alias": row["alias"].text().strip() or f"t{idx + 2}",
                "conditions": conditions,
            })
        return joins

    def _collect(panel):
        # previous_collect 是 V2 在安装最终版之前的真实实现，不会递归回最终版。
        qb = previous_collect(panel)
        join_mode = panel._radio_join_v3.isChecked()
        db, table = _source_ref(panel)
        qb.database_name = db
        qb.schema_name = ""
        qb.table_name = table
        qb.qualify_database = len(_selected(panel)) > 1
        qb.joins = _collect_joins(panel) if join_mode else []
        qb.source_alias = "t1" if qb.joins else ""
        ftext = panel._cmb_field.currentText().strip()
        qb.field_name = (getattr(panel, "_field_display_lookup", {}) or {}).get(ftext, ftext)
        filters = []
        for idx, fr in enumerate(getattr(panel, "_filter_rows", []) or []):
            text = fr["field_combo"].currentText().strip()
            value = fr["value"].text().strip()
            if not text and not value:
                continue
            filters.append({
                "connector": "where" if idx == 0 else fr["connector"].currentText(),
                "field": (getattr(panel, "_field_display_lookup", {}) or {}).get(text, text),
                "op": SQL_OPERATORS[fr["op"].currentIndex()],
                "value": value,
            })
        qb.filters = filters
        return qb

    def _commit(panel, *_args):
        if getattr(panel, "_suppress_update", False) or getattr(panel, "_v2_loading", False):
            return
        qb = _collect(panel)
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
        qb = _collect(panel)
        if not qb.table_name or not qb.joins or qb.validate_joins():
            return False
        return all(j.get("table_name") and j.get("conditions") for j in qb.joins)

    def _quote_table(panel, db, table):
        cfg = panel._template.db_configs.get("default")
        db_type = (getattr(cfg, "db_type", "mysql") or "mysql").lower()
        if db_type == "mysql":
            return f"`{db.replace('`', '``')}`.`{table.replace('`', '``')}`" if db else f"`{table.replace('`', '``')}`"
        parts = table.split(".", 1)
        schema, raw = (parts[0], parts[1]) if len(parts) == 2 else ("dbo", table)
        return ".".join(f"[{part.replace(']', ']]')}]" for part in (db, schema, raw) if part)

    class _DataPreview(QDialog):
        def __init__(self, panel):
            super().__init__(panel.window())
            self.panel = panel
            self.setWindowTitle("数据案例预览")
            self.resize(1180, 650)
            self.setModal(False)
            root = QVBoxLayout(self)
            self.info = QLabel("尚未选择数据表")
            self.info.setWordWrap(True)
            root.addWidget(self.info)
            tools = QHBoxLayout()
            tools.addWidget(QLabel("显示行数:"))
            self.limit = QComboBox(); self.limit.addItems(["10", "20", "50", "100"]); self.limit.setCurrentText("20")
            refresh = QPushButton("刷新")
            refresh.clicked.connect(lambda: _refresh_preview(self.panel, True))
            tools.addWidget(self.limit); tools.addWidget(refresh); tools.addStretch(1)
            root.addLayout(tools)
            self.table = QTableWidget()
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setAlternatingRowColors(True)
            root.addWidget(self.table, 1)
            self.status = QLabel(""); self.status.setStyleSheet("color:#666;")
            root.addWidget(self.status)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.hide)
            root.addWidget(buttons)

        def closeEvent(self, event):
            event.ignore(); self.hide()

    def _preview(panel):
        obj = getattr(panel, "_data_preview_v3", None)
        if obj is None:
            obj = _DataPreview(panel)
            panel._data_preview_v3 = obj
        return obj

    def _preview_headers(panel, qb, raw):
        if not qb.joins:
            return list(raw)
        sources = _sources(panel)
        expected, counts, table_counts = [], {}, {}
        for src in sources:
            table_counts[src["table"]] = table_counts.get(src["table"], 0) + 1
            for col in src["columns"]:
                counts[col] = counts.get(col, 0) + 1
                expected.append((col, src))
        if len(expected) != len(raw):
            return list(raw)
        headers = []
        for col, src in expected:
            if counts.get(col, 0) == 1:
                headers.append(col)
            else:
                source = src["table"] if table_counts.get(src["table"], 0) == 1 else f'{src["db"]}.{src["table"]}'
                headers.append(f"{col} ({source})")
        return headers

    def _refresh_preview(panel, force=False):
        editor = getattr(panel, "_editor", None)
        if editor is None:
            return False
        cfg = editor._template.db_configs.get("default")
        if cfg is None:
            return False
        join_mode = panel._radio_join_v3.isChecked()
        qb = _collect(panel)
        window = _preview(panel)
        limit = int(window.limit.currentText())
        if join_mode:
            # 配置不完整时保持上一份有效预览，既不清空也不执行半成品 SQL。
            if not _join_complete(panel):
                return False
            sql = qb.build_join_preview_sql(limit, cfg.db_type)
            info = "合并结果：" + " + ".join([qb.table_name] + [j.get("table_name", "") for j in qb.joins])
            switch_db = qb.database_name if len(_selected(panel)) == 1 else ""
        else:
            db, table = _source_ref(panel)
            if not db or not table:
                return False
            qualified = _quote_table(panel, db, table)
            if (getattr(cfg, "db_type", "mysql") or "mysql").lower() == "sqlserver":
                sql = f"SELECT TOP {limit} * FROM {qualified}"
            else:
                sql = f"SELECT * FROM {qualified} LIMIT {limit}"
            info = f"数据表：{_display_table(panel, db, table)}"
            switch_db = db if len(_selected(panel)) == 1 else ""

        if not editor._db_handler.is_connected("default") and not editor._db_handler.connect(cfg, "default"):
            if force:
                QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "数据库连接失败")
            return False
        result = editor._db_handler.execute_rows(sql, "default", switch_db)
        if result is None:
            if force:
                QMessageBox.critical(panel, "预览失败", editor._db_handler.last_error or "查询失败")
            return False
        raw, rows = result
        headers = _preview_headers(panel, qb, raw)
        window.table.clear()
        window.table.setColumnCount(len(headers))
        window.table.setHorizontalHeaderLabels(headers)
        window.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                window.table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        window.table.resizeColumnsToContents()
        window.info.setText(info)
        window.status.setText(
            f"显示 {len(rows)} 行 | " +
            ("关联信息完整后自动更新；不完整时保留上一结果" if join_mode else "选择数据表后自动更新")
        )
        window.show(); window.raise_(); window.activateWindow()
        panel._last_preview_sql_v3 = sql
        return True

    def _auto_preview(panel):
        if getattr(panel, "_v2_loading", False):
            return
        if panel._radio_join_v3.isChecked() and not _join_complete(panel):
            return
        QTimer.singleShot(120, lambda: _refresh_preview(panel, False))

    def _left_table_changed(panel, row):
        if getattr(panel, "_join_rows", []) and row is panel._join_rows[0]:
            _sync_hidden_source(panel)
            _refresh_fields(panel)
            _commit(panel)
            _auto_preview(panel)

    def _right_table_changed(panel, row):
        _right_ref(panel, row)
        _refresh_fields(panel)
        _commit(panel)
        _auto_preview(panel)

    def _set_mode(panel, join_mode):
        panel._radio_single_v3.blockSignals(True); panel._radio_join_v3.blockSignals(True)
        panel._radio_single_v3.setChecked(not join_mode); panel._radio_join_v3.setChecked(join_mode)
        panel._radio_single_v3.blockSignals(False); panel._radio_join_v3.blockSignals(False)
        panel._cmb_table.setVisible(not join_mode)
        if panel._table_label_v3 is not None:
            panel._table_label_v3.setVisible(not join_mode)
        panel._join_group_v2.setVisible(join_mode)
        if join_mode and not getattr(panel, "_join_rows", []):
            panel._add_join_row_v2()
        _refresh_table_choices(panel)
        _refresh_fields(panel)
        _commit(panel)
        _auto_preview(panel)

    def _single_table_changed(panel):
        if panel._radio_join_v3.isChecked():
            return
        _sync_hidden_source(panel)
        _refresh_fields(panel)
        _commit(panel)
        _auto_preview(panel)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        _hide_database(self)
        self._table_label_v3 = _find_label(self, "数据表:")
        old_field_label = _find_label(self, "字段:")
        if old_field_label is not None:
            old_field_label.hide()

        builder = self._builder_widget.layout()
        source_group = QGroupBox("数据来源")
        sl = QHBoxLayout(source_group)
        sl.setContentsMargins(6, 5, 6, 5)
        self._radio_single_v3 = QRadioButton("单表")
        self._radio_join_v3 = QRadioButton("表关联")
        self._radio_single_v3.setChecked(True)
        sl.addWidget(self._radio_single_v3); sl.addWidget(self._radio_join_v3); sl.addStretch(1)
        builder.insertWidget(1, source_group)

        # 数据案例预览入口前置到数据来源区域；预览窗非模态，可边看边继续配置。
        preview_row = QWidget()
        pl = QHBoxLayout(preview_row); pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(QLabel("数据案例预览:"))
        self._btn_preview_join_v2.setText("打开 / 刷新预览")
        self._btn_preview_join_v2.setToolTip("单表选中后自动刷新；JOIN 全部填写完成后才刷新合并结果")
        pl.addWidget(self._btn_preview_join_v2); pl.addStretch(1)
        builder.insertWidget(2, preview_row)
        try:
            self._btn_preview_join_v2.clicked.disconnect()
        except TypeError:
            pass
        self._btn_preview_join_v2.clicked.connect(lambda: _refresh_preview(self, True))

        # 返回字段统一移到 JOIN 后；多表时先完成合并再选返回字段。
        return_row = QWidget()
        rl = QHBoxLayout(return_row); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("返回字段:")); rl.addWidget(self._cmb_field, 1)
        join_index = builder.indexOf(self._join_group_v2)
        builder.insertWidget(join_index + 1 if join_index >= 0 else builder.count(), return_row)
        self._return_row_v3 = return_row

        _enhance_combo(self._cmb_table); _enhance_combo(self._cmb_field)
        self._radio_single_v3.toggled.connect(lambda checked: checked and _set_mode(self, False))
        self._radio_join_v3.toggled.connect(lambda checked: checked and _set_mode(self, True))
        self._cmb_table.activated.connect(lambda *_: _single_table_changed(self))
        self._cmb_table.lineEdit().editingFinished.connect(lambda: _single_table_changed(self))
        _refresh_table_choices(self)
        _set_mode(self, False)

    def refresh_metadata(self):
        result = previous_refresh_metadata(self)
        _hide_database(self)
        _refresh_table_choices(self)
        _refresh_fields(self)
        return result

    def add_condition(self, row, data=None):
        result = previous_add_condition(self, row, data)
        if row.get("conditions"):
            _decorate_condition(self, row, row["conditions"][-1])
        _refresh_join_fields(self, row)
        return result

    def add_join(self, data=None):
        result = previous_add_join(self, data)
        if self._join_rows:
            _decorate_row(self, self._join_rows[-1])
        _layout_rows(self); _refresh_fields(self)
        return result

    def move_join(self, row, delta):
        result = previous_move_join(self, row, delta)
        _layout_rows(self); _refresh_fields(self); _commit(self); _auto_preview(self)
        return result

    def remove_join(self, row):
        result = previous_remove_join(self, row)
        _layout_rows(self); _refresh_fields(self); _commit(self); _auto_preview(self)
        return result

    def load_binding(self):
        result = previous_load(self)
        if self._current_row < 0 or self._current_col < 0:
            return result
        qb = self._template.get_cell_data(self._current_row, self._current_col).query_binding
        _refresh_table_choices(self)
        if qb is None:
            _set_mode(self, False)
            return result
        if qb.database_name and qb.table_name:
            self._cmb_table.blockSignals(True)
            self._cmb_table.setCurrentText(_display_table(self, qb.database_name, qb.table_name))
            self._cmb_table.blockSignals(False)
        _set_mode(self, bool(qb.joins))
        if qb.joins and self._join_rows:
            first = self._join_rows[0]
            _decorate_row(self, first)
            first["left_table_v3"].blockSignals(True)
            first["left_table_v3"].setCurrentText(_display_table(self, qb.database_name, qb.table_name))
            first["left_table_v3"].blockSignals(False)
        _layout_rows(self); _refresh_fields(self)
        display_field = qb.field_name
        for display, sql_value in (getattr(self, "_field_display_lookup", {}) or {}).items():
            if sql_value == qb.field_name:
                display_field = display; break
        self._cmb_field.blockSignals(True); self._cmb_field.setCurrentText(display_field); self._cmb_field.blockSignals(False)
        return result

    def update_state(self):
        result = previous_update_state(self)
        if hasattr(self, "_btn_preview_join_v2"):
            self._btn_preview_join_v2.setEnabled(self._chk_db_enabled.isChecked())
        return result

    def join_changed(self, *_args):
        if getattr(self, "_suppress_update", False) or getattr(self, "_v2_loading", False):
            return
        _layout_rows(self); _refresh_fields(self); _commit(self); _auto_preview(self)

    def refresh_identifiers(self, *_args):
        _refresh_fields(self)

    cls.__init__ = panel_init
    cls.refresh_database_metadata = refresh_metadata
    cls._add_join_condition_v2 = add_condition
    cls._add_join_row_v2 = add_join
    cls._move_join_v2 = move_join
    cls._remove_join_v2 = remove_join
    cls._load_db_binding = load_binding
    cls._update_db_ui_state = update_state
    cls._on_join_changed_v2 = join_changed
    cls._refresh_identifier_choices = refresh_identifiers
    cls._refresh_identifier_choices_v2 = refresh_identifiers
    cls._collect_db_binding = _collect
    cls._collect_binding_v2 = _collect
    cls._commit_binding_v2 = _commit
    cls._on_db_config_changed = _commit
    cls._preview_join_result_v2 = lambda self: _refresh_preview(self, True)

    # 时间字段跟随当前合并后的真实 SQL 字段，而不是只看原始主表。
    def sync_time_fields(self, *_args):
        panel = self._db_panel
        if hasattr(panel, "_radio_join_v3") and panel._radio_join_v3.isChecked():
            values = list(getattr(panel, "_merged_field_sql_v3", []) or [])
        else:
            db, table = _source_ref(panel)
            values = _columns(panel, db, table)
        self._time_panel.set_field_choices(values)

    ww.WorkspaceWindow._sync_time_field_choices = sync_time_fields

    # 数据库侧默认更宽，JOIN 每项也已改为两行，不再把所有输入塞在 LEFT JOIN 后面。
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
