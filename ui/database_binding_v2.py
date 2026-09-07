"""数据库绑定 V2：多 JOIN、包含式搜索输入和合并结果预览。"""


def install_database_binding_v2():
    import ui.editor_side_panels as esp
    from models.db_config import SQL_OPERATORS, JOIN_OPERATORS
    from PyQt6.QtCore import Qt, QEvent, QObject, QTimer, QStringListModel
    from PyQt6.QtWidgets import (
        QAbstractItemView, QComboBox, QCompleter, QDialog, QDialogButtonBox,
        QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
        QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )

    if getattr(esp, "_database_binding_v2_installed", False):
        return
    esp._database_binding_v2_installed = True

    class _CompleterPopupFilter(QObject):
        """获得焦点即展开候选，但不让下拉列表抢走文本编辑焦点。"""

        def __init__(self, combo):
            super().__init__(combo)
            self.combo = combo

        def eventFilter(self, watched, event):
            if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
                QTimer.singleShot(0, self._show)
            return False

        def _show(self):
            combo = self.combo
            if not combo.isEnabled() or not combo.isVisible() or not combo.isEditable():
                return
            completer = combo.completer()
            if completer is None:
                return
            completer.setCompletionPrefix(combo.lineEdit().text())
            completer.complete()

    def _set_search_choices(combo, choices, preserve=True):
        values = list(dict.fromkeys(str(item) for item in (choices or []) if str(item)))
        current = combo.currentText() if preserve else ""
        combo._search_choices = values
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        if combo.isEditable():
            combo.setEditText(current)
        elif current in values:
            combo.setCurrentText(current)
        elif values:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        model = getattr(combo, "_search_model", None)
        if model is not None:
            model.setStringList(values)

    def _configure_search_combo(panel, combo):
        if combo is None:
            return
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        choices = [combo.itemText(i) for i in range(combo.count())]
        model = QStringListModel(choices, combo)
        completer = QCompleter(model, combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
        combo._search_model = model
        combo._search_choices = choices
        line_edit = combo.lineEdit()
        if not hasattr(combo, "_contains_popup_filter"):
            popup_filter = _CompleterPopupFilter(combo)
            line_edit.installEventFilter(popup_filter)
            combo._contains_popup_filter = popup_filter
        if not combo.property("contains_search_connected"):
            def on_text_edited(text, c=combo):
                comp = c.completer()
                if comp is not None:
                    comp.setCompletionPrefix(text)
                    comp.complete()
            line_edit.textEdited.connect(on_text_edited)
            combo.setProperty("contains_search_connected", True)

    def _db_type(panel):
        cfg = panel._template.db_configs.get("default") if panel._template else None
        return (getattr(cfg, "db_type", "mysql") or "mysql").lower()

    def _split_table_key(panel, table_key):
        table_key = (table_key or "").strip()
        if _db_type(panel) == "sqlserver" and "." in table_key:
            schema, table = table_key.split(".", 1)
            return schema, table
        return "", table_key

    def _table_key(schema, table):
        return f"{schema}.{table}" if schema else table

    def _source_database(panel):
        return panel._cmb_database.currentText().strip() if hasattr(panel, "_cmb_database") else ""

    def _source_table(panel):
        return panel._cmb_table.currentText().strip()

    def _columns(panel, database, table):
        all_meta = getattr(panel, "_all_db_metadata", {}) or {}
        return list((all_meta.get(database, {}) or {}).get(table, []) or [])

    def _sources(panel, upto=None):
        join_rows = list(getattr(panel, "_join_rows", []) or [])
        use_rows = join_rows if upto is None else join_rows[:upto]
        result = []
        source_db = _source_database(panel)
        source_table = _source_table(panel)
        source_alias = "t1" if join_rows else ""
        if source_table:
            result.append({
                "database": source_db,
                "table": source_table,
                "alias": source_alias or source_table.split(".")[-1],
                "columns": _columns(panel, source_db, source_table),
            })
        for index, row in enumerate(use_rows):
            database = row["database"].currentText().strip() or source_db
            table = row["table"].currentText().strip()
            if not table:
                continue
            alias = row["alias"].text().strip() or f"t{index + 2}"
            result.append({
                "database": database, "table": table, "alias": alias,
                "columns": _columns(panel, database, table),
            })
        return result

    def _field_candidates(panel):
        sources = _sources(panel)
        field_counts = {}
        table_counts = {}
        for src in sources:
            table_counts[src["table"]] = table_counts.get(src["table"], 0) + 1
            for column in src["columns"]:
                field_counts[column] = field_counts.get(column, 0) + 1
        choices, lookup = [], {}
        for src in sources:
            for column in src["columns"]:
                if field_counts.get(column, 0) == 1:
                    display = column
                else:
                    source_name = src["table"]
                    if table_counts.get(src["table"], 0) > 1:
                        source_name = f'{src["database"]}.{src["table"]}'
                    display = f"{column} ({source_name})"
                if display in lookup:
                    display = f'{column} ({src["database"]}.{src["table"]})'
                lookup[display] = f'{src["alias"]}.{column}' if src["alias"] else column
                choices.append(display)
        return choices, lookup

    def _reverse_lookup(lookup, value):
        for display, sql_value in lookup.items():
            if sql_value == value:
                return display
        return value

    esp.DatabaseBindingPanel._configure_identifier_combo = _configure_search_combo
    esp.DatabaseBindingPanel._set_combo_choices = staticmethod(_set_search_choices)

    previous_init = esp.DatabaseBindingPanel.__init__
    previous_collect = esp.DatabaseBindingPanel._collect_db_binding
    previous_load = esp.DatabaseBindingPanel._load_db_binding
    previous_update_state = esp.DatabaseBindingPanel._update_db_ui_state

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        provider = kwargs.get("metadata_provider")
        self._editor = getattr(provider, "__self__", None)
        self._join_rows = []
        self._field_display_lookup = {}
        self._v2_loading = False

        self._chk_use_joins.hide()
        self._lbl_joins.hide()
        self._join_widget.hide()

        builder_layout = self._builder_widget.layout()
        self._join_group_v2 = QGroupBox("表关联 JOIN（0）")
        jl = QVBoxLayout(self._join_group_v2)
        jl.setContentsMargins(6, 8, 6, 6)
        help_label = QLabel("用于将多张数据表按照字段关系组合。")
        help_label.setStyleSheet("color:#777; font-size:11px;")
        jl.addWidget(help_label)
        self._joins_container_v2 = QWidget()
        self._joins_layout_v2 = QVBoxLayout(self._joins_container_v2)
        self._joins_layout_v2.setContentsMargins(0, 0, 0, 0)
        self._joins_layout_v2.setSpacing(6)
        jl.addWidget(self._joins_container_v2)
        self._btn_add_join_v2 = QPushButton("+ 添加关联")
        self._btn_add_join_v2.clicked.connect(self._add_join_row_v2)
        jl.addWidget(self._btn_add_join_v2)
        builder_layout.addWidget(self._join_group_v2)

        for label in self.findChildren(QLabel):
            if label.text().strip().startswith("筛选条件"):
                label.hide()
        for button in self.findChildren(QPushButton):
            if button.text() in ("+ 条件", "- 条件"):
                button.hide()

        self._filter_group_v2 = QGroupBox("数据筛选 WHERE")
        fl = QVBoxLayout(self._filter_group_v2)
        fl.setContentsMargins(6, 8, 6, 6)
        filter_help = QLabel("用于从组合后的数据中筛选需要的记录。")
        filter_help.setStyleSheet("color:#777; font-size:11px;")
        fl.addWidget(filter_help)
        self._filters_container.setParent(self._filter_group_v2)
        fl.addWidget(self._filters_container)
        self._btn_add_filter_v2 = QPushButton("+ 添加条件")
        self._btn_add_filter_v2.clicked.connect(self._add_filter_row)
        fl.addWidget(self._btn_add_filter_v2)
        builder_layout.addWidget(self._filter_group_v2)

        self._clear_filter_rows_v2()
        self._add_filter_row_v2()

        self._lbl_identifier_warning_v2 = QLabel("")
        self._lbl_identifier_warning_v2.setWordWrap(True)
        self._lbl_identifier_warning_v2.setStyleSheet("color:#B06000; font-size:11px;")
        builder_layout.addWidget(self._lbl_identifier_warning_v2)

        self._btn_preview_join_v2 = QPushButton("预览合并结果")
        self._btn_preview_join_v2.setToolTip("只查看主表与所有 JOIN 合并后的前几行，不应用 WHERE、时间或聚合")
        self._btn_preview_join_v2.clicked.connect(self._preview_join_result_v2)
        page = self._lbl_sql_preview.parentWidget()
        page_layout = page.layout()
        idx = page_layout.indexOf(self._lbl_sql_preview)
        page_layout.insertWidget(idx + 1 if idx >= 0 else page_layout.count(), self._btn_preview_join_v2)

        for combo in (self._cmb_table, self._cmb_field):
            _configure_search_combo(self, combo)
        if hasattr(self, "_cmb_database"):
            try:
                self._cmb_database.currentTextChanged.disconnect()
            except TypeError:
                pass
            _configure_search_combo(self, self._cmb_database)
            self._cmb_database.activated.connect(lambda *_: self._on_database_finished_v2())
            self._cmb_database.lineEdit().editingFinished.connect(self._on_database_finished_v2)

        self._txt_table.editingFinished.connect(self._validate_identifiers_v2)
        self._txt_field.editingFinished.connect(self._validate_identifiers_v2)
        self._refresh_identifier_choices_v2()
        self._update_db_ui_state_v2()

    def _clear_filter_rows_v2(self):
        for fr in list(getattr(self, "_filter_rows", [])):
            widget = fr.get("widget")
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._filter_rows = []

    def _add_filter_row_v2(self):
        row_widget = QWidget()
        lay = QHBoxLayout(row_widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        connector = QComboBox(); connector.setFixedWidth(58)
        if self._filter_rows:
            connector.addItems(["and", "or"])
        else:
            connector.addItems(["where"]); connector.setEnabled(False)
        field_combo = QComboBox(); _configure_search_combo(self, field_combo)
        field_combo.lineEdit().setPlaceholderText("选择或输入筛选字段")
        op = QComboBox()
        from models.db_config import SQL_OPERATOR_LABELS
        op.addItems([SQL_OPERATOR_LABELS[o] for o in SQL_OPERATORS]); op.setFixedWidth(74)
        value = QLineEdit(); value.setPlaceholderText("值")
        remove = QPushButton("×"); remove.setFixedWidth(28)
        lay.addWidget(connector); lay.addWidget(field_combo, 1); lay.addWidget(op)
        lay.addWidget(value, 1); lay.addWidget(remove)
        self._filters_layout.addWidget(row_widget)
        record = {"widget": row_widget, "connector": connector, "field_combo": field_combo,
                  "field": field_combo.lineEdit(), "op": op, "value": value, "remove": remove}
        self._filter_rows.append(record)
        connector.currentTextChanged.connect(self._commit_binding_v2)
        field_combo.lineEdit().textChanged.connect(self._commit_binding_v2)
        op.currentIndexChanged.connect(self._commit_binding_v2)
        value.textChanged.connect(self._commit_binding_v2)
        remove.clicked.connect(lambda: self._remove_filter_row_v2(record))
        choices, _ = _field_candidates(self)
        _set_search_choices(field_combo, choices)

    def _remove_filter_row_v2(self, record):
        if record not in self._filter_rows:
            return
        self._filter_rows.remove(record)
        record["widget"].setParent(None); record["widget"].deleteLater()
        if not self._filter_rows:
            self._add_filter_row_v2()
        else:
            first = self._filter_rows[0]["connector"]
            first.blockSignals(True); first.clear(); first.addItem("where"); first.setEnabled(False); first.blockSignals(False)
        self._commit_binding_v2()

    def _join_types_v2(self):
        values = ["LEFT JOIN", "INNER JOIN", "RIGHT JOIN"]
        if _db_type(self) == "sqlserver":
            values.append("FULL JOIN")
        return values

    def _add_join_condition_v2(self, join_row, data=None):
        data = data or {}
        widget = QWidget(); lay = QHBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(3)
        connector = QComboBox(); connector.setFixedWidth(58)
        if join_row["conditions"]:
            connector.addItems(["AND", "OR"])
        else:
            connector.addItem("AND"); connector.setEnabled(False)
        left = QComboBox(); right = QComboBox()
        _configure_search_combo(self, left); _configure_search_combo(self, right)
        op = QComboBox(); op.addItems(JOIN_OPERATORS); op.setFixedWidth(58)
        remove = QPushButton("×"); remove.setFixedWidth(28)
        lay.addWidget(connector); lay.addWidget(left, 1); lay.addWidget(op); lay.addWidget(right, 1); lay.addWidget(remove)
        join_row["conditions_layout"].addWidget(widget)
        condition = {"widget": widget, "connector": connector, "left": left, "op": op, "right": right, "remove": remove}
        join_row["conditions"].append(condition)
        connector.setCurrentText(str(data.get("connector", "AND")).upper())
        left.setCurrentText(data.get("left", "")); op.setCurrentText(data.get("op", "=")); right.setCurrentText(data.get("right", ""))
        connector.currentTextChanged.connect(self._on_join_changed_v2)
        left.currentTextChanged.connect(self._on_join_changed_v2)
        op.currentTextChanged.connect(self._on_join_changed_v2)
        right.currentTextChanged.connect(self._on_join_changed_v2)
        remove.clicked.connect(lambda: self._remove_join_condition_v2(join_row, condition))

    def _remove_join_condition_v2(self, join_row, condition):
        if condition not in join_row["conditions"]:
            return
        join_row["conditions"].remove(condition)
        condition["widget"].setParent(None); condition["widget"].deleteLater()
        if not join_row["conditions"]:
            self._add_join_condition_v2(join_row)
        self._refresh_join_row_v2(join_row); self._on_join_changed_v2()

    def _add_join_row_v2(self, data=None):
        data = data or {}
        frame = QFrame(); frame.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(frame); root.setContentsMargins(5, 5, 5, 5); root.setSpacing(4)
        top = QHBoxLayout()
        number = QLabel(""); number.setMinimumWidth(18)
        join_type = QComboBox(); join_type.addItems(self._join_types_v2())
        database = QComboBox(); table = QComboBox()
        _configure_search_combo(self, database); _configure_search_combo(self, table)
        alias = QLineEdit(); alias.setPlaceholderText("别名"); alias.setMaximumWidth(72)
        up = QPushButton("↑"); down = QPushButton("↓"); remove = QPushButton("×")
        for button in (up, down, remove): button.setFixedWidth(28)
        top.addWidget(number); top.addWidget(join_type); top.addWidget(database, 1); top.addWidget(table, 1)
        top.addWidget(alias); top.addWidget(up); top.addWidget(down); top.addWidget(remove); root.addLayout(top)
        conditions_widget = QWidget(); conditions_layout = QVBoxLayout(conditions_widget)
        conditions_layout.setContentsMargins(0, 0, 0, 0); conditions_layout.setSpacing(3); root.addWidget(conditions_widget)
        add_condition = QPushButton("+ 条件"); add_condition.setMaximumWidth(82); root.addWidget(add_condition, 0, Qt.AlignmentFlag.AlignLeft)
        row = {"widget": frame, "number": number, "type": join_type, "database": database, "table": table,
               "alias": alias, "up": up, "down": down, "remove": remove,
               "conditions_layout": conditions_layout, "conditions": [], "add_condition": add_condition}
        self._join_rows.append(row); self._joins_layout_v2.addWidget(frame)
        selected = list(getattr(self._template, "selected_databases", []) or [])
        _set_search_choices(database, selected, preserve=False)
        database.setCurrentText(data.get("database_name") or _source_database(self))
        self._refresh_join_table_v2(row)
        raw_table = data.get("table_name") or data.get("table") or ""
        db_name = database.currentText().strip()
        if db_name and raw_table.startswith(db_name + "."):
            raw_table = raw_table[len(db_name) + 1:]
        if data.get("schema_name"):
            raw_table = _table_key(data.get("schema_name"), raw_table)
        table.setCurrentText(raw_table)
        join_type.setCurrentText(data.get("type", "LEFT JOIN"))
        alias.setText(data.get("alias") or f"t{len(self._join_rows) + 1}")
        conditions = data.get("conditions") or []
        if not conditions and data.get("on"):
            parts = str(data.get("on")).split("=", 1)
            if len(parts) == 2:
                conditions = [{"left": parts[0].strip(), "op": "=", "right": parts[1].strip()}]
        for item in conditions or [{}]: self._add_join_condition_v2(row, item)
        join_type.currentTextChanged.connect(self._on_join_changed_v2)
        database.activated.connect(lambda *_: self._on_join_database_v2(row))
        database.lineEdit().editingFinished.connect(lambda: self._on_join_database_v2(row))
        table.currentTextChanged.connect(lambda *_: self._on_join_table_v2(row))
        alias.textChanged.connect(self._on_join_changed_v2)
        up.clicked.connect(lambda: self._move_join_v2(row, -1)); down.clicked.connect(lambda: self._move_join_v2(row, 1))
        remove.clicked.connect(lambda: self._remove_join_v2(row))
        add_condition.clicked.connect(lambda: (self._add_join_condition_v2(row), self._refresh_join_row_v2(row)))
        self._renumber_joins_v2(); self._refresh_join_row_v2(row); self._refresh_identifier_choices_v2()

    def _refresh_join_table_v2(self, row):
        database = row["database"].currentText().strip() or _source_database(self)
        tables = sorted((getattr(self, "_all_db_metadata", {}).get(database, {}) or {}).keys(), key=str.lower)
        _set_search_choices(row["table"], tables)

    def _refresh_join_row_v2(self, row):
        if row not in self._join_rows: return
        index = self._join_rows.index(row)
        left_choices = []
        for src in _sources(self, index):
            left_choices.extend(f'{src["alias"]}.{col}' for col in src["columns"])
        database = row["database"].currentText().strip() or _source_database(self)
        table = row["table"].currentText().strip()
        alias = row["alias"].text().strip() or f"t{index + 2}"
        right_choices = [f"{alias}.{col}" for col in _columns(self, database, table)]
        for condition in row["conditions"]:
            _set_search_choices(condition["left"], left_choices)
            _set_search_choices(condition["right"], right_choices)

    def _on_join_database_v2(self, row):
        self._refresh_join_table_v2(row); self._refresh_join_row_v2(row); self._on_join_changed_v2()

    def _on_join_table_v2(self, row):
        self._refresh_join_row_v2(row); self._on_join_changed_v2()

    def _renumber_joins_v2(self):
        for index, row in enumerate(self._join_rows):
            row["number"].setText(f"{index + 1}.")
            row["up"].setEnabled(index > 0); row["down"].setEnabled(index < len(self._join_rows) - 1)
        self._join_group_v2.setTitle(f"表关联 JOIN（{len(self._join_rows)}）")

    def _move_join_v2(self, row, delta):
        if row not in self._join_rows: return
        old = self._join_rows.index(row); new = old + delta
        if new < 0 or new >= len(self._join_rows): return
        self._join_rows.pop(old); self._join_rows.insert(new, row)
        self._joins_layout_v2.removeWidget(row["widget"]); self._joins_layout_v2.insertWidget(new, row["widget"])
        self._renumber_joins_v2(); self._refresh_all_join_choices_v2(); self._on_join_changed_v2()

    def _remove_join_v2(self, row):
        if row not in self._join_rows: return
        self._join_rows.remove(row); row["widget"].setParent(None); row["widget"].deleteLater()
        self._renumber_joins_v2(); self._refresh_all_join_choices_v2(); self._on_join_changed_v2()

    def _clear_joins_v2(self):
        for row in list(self._join_rows): row["widget"].setParent(None); row["widget"].deleteLater()
        self._join_rows = []; self._renumber_joins_v2()

    def _refresh_all_join_choices_v2(self):
        for row in self._join_rows:
            self._refresh_join_table_v2(row); self._refresh_join_row_v2(row)
        self._refresh_identifier_choices_v2()

    def _collect_joins_v2(self):
        result = []
        source_db = _source_database(self)
        for index, row in enumerate(self._join_rows):
            database = row["database"].currentText().strip() or source_db
            schema, table_name = _split_table_key(self, row["table"].currentText().strip())
            conditions = []
            for ci, cond in enumerate(row["conditions"]):
                left = cond["left"].currentText().strip(); right = cond["right"].currentText().strip()
                if not left and not right: continue
                conditions.append({"connector": "AND" if ci == 0 else cond["connector"].currentText().upper(),
                                   "left": left, "op": cond["op"].currentText() or "=", "right": right})
            result.append({"type": row["type"].currentText(), "database_name": database,
                           "schema_name": schema, "table_name": table_name,
                           "alias": row["alias"].text().strip() or f"t{index + 2}", "conditions": conditions})
        return result

    def _refresh_identifier_choices_v2(self, *_args):
        choices, lookup = _field_candidates(self)
        self._field_display_lookup = lookup
        _set_search_choices(self._cmb_field, choices)
        for fr in self._filter_rows: _set_search_choices(fr["field_combo"], choices)
        for row in self._join_rows: self._refresh_join_row_v2(row)

    def _collect_binding_v2(self):
        qb = previous_collect(self)
        selected = list(getattr(self._template, "selected_databases", []) or [])
        database = _source_database(self); schema, table_name = _split_table_key(self, _source_table(self))
        joins = self._collect_joins_v2()
        qb.database_name = database; qb.schema_name = schema; qb.table_name = table_name
        qb.qualify_database = len(selected) > 1; qb.source_alias = "t1" if joins else ""; qb.joins = joins
        field_text = self._cmb_field.currentText().strip(); qb.field_name = self._field_display_lookup.get(field_text, field_text)
        filters = []
        for index, fr in enumerate(self._filter_rows):
            field_text = fr["field_combo"].currentText().strip(); value = fr["value"].text().strip()
            if not field_text and not value: continue
            filters.append({"connector": "where" if index == 0 else fr["connector"].currentText(),
                            "field": self._field_display_lookup.get(field_text, field_text),
                            "op": SQL_OPERATORS[fr["op"].currentIndex()], "value": value})
        qb.filters = filters
        return qb

    def _commit_binding_v2(self, *_args):
        if self._suppress_update or self._v2_loading: return
        qb = self._collect_binding_v2()
        self._apply_db_patch({"enabled": qb.enabled, "query_type": qb.query_type, "db_config_key": qb.db_config_key,
                              "database_name": qb.database_name, "schema_name": qb.schema_name,
                              "qualify_database": qb.qualify_database, "table_name": qb.table_name,
                              "source_alias": qb.source_alias, "field_name": qb.field_name,
                              "aggregate_func": qb.aggregate_func, "sql_mode": qb.sql_mode,
                              "custom_sql": qb.custom_sql, "sync_modes": qb.sync_modes,
                              "joins": qb.joins, "filters": qb.filters, "date_placeholder": qb.date_placeholder})
        self._validate_identifiers_v2()

    def _on_join_changed_v2(self, *_args):
        if self._suppress_update or self._v2_loading: return
        self._renumber_joins_v2(); self._refresh_all_join_choices_v2(); self._commit_binding_v2()

    def _on_database_finished_v2(self):
        if hasattr(self, "_on_project_database_changed"):
            self._on_project_database_changed(self._cmb_database.currentText())
        self._refresh_all_join_choices_v2(); self._commit_binding_v2()

    def _validate_identifiers_v2(self):
        database = _source_database(self); table = _source_table(self); field = self._cmb_field.currentText().strip()
        tables = (getattr(self, "_all_db_metadata", {}).get(database, {}) or {})
        messages = []
        if table and table not in tables: messages.append("当前数据库结构中未找到该数据表")
        if field and field not in self._field_display_lookup and field not in set(self._field_display_lookup.values()):
            messages.append("当前合并字段中未找到该返回字段")
        self._lbl_identifier_warning_v2.setText("⚠ " + "；".join(messages) if messages else "")

    def _load_binding_v2(self):
        self._v2_loading = True
        try:
            previous_load(self)
            if self._current_row < 0 or self._current_col < 0: return
            qb = self._template.get_cell_data(self._current_row, self._current_col).query_binding
            if qb is None: return
            if hasattr(self, "_populate_project_databases"):
                self._populate_project_databases(qb.database_name or _source_database(self))
            if hasattr(self, "_apply_project_database"):
                self._apply_project_database(self._cmb_database.currentText().strip())
            self._cmb_table.blockSignals(True); self._cmb_table.setCurrentText(_table_key(qb.schema_name, qb.table_name)); self._cmb_table.blockSignals(False)
            self._clear_joins_v2()
            for join in qb.joins or []: self._add_join_row_v2(join)
            self._refresh_all_join_choices_v2()
            display = _reverse_lookup(self._field_display_lookup, qb.field_name)
            self._cmb_field.blockSignals(True); self._cmb_field.setCurrentText(display); self._cmb_field.blockSignals(False)
            for fr, item in zip(self._filter_rows, qb.filters or []):
                fr["field_combo"].blockSignals(True)
                fr["field_combo"].setCurrentText(_reverse_lookup(self._field_display_lookup, item.get("field", "")))
                fr["field_combo"].blockSignals(False)
        finally:
            self._v2_loading = False
        self._renumber_joins_v2(); self._refresh_identifier_choices_v2(); self._update_sql_preview(); self._validate_identifiers_v2()

    def _update_db_ui_state_v2(self):
        previous_update_state(self)
        enabled = self._chk_db_enabled.isChecked()
        self._join_group_v2.setEnabled(enabled); self._filter_group_v2.setEnabled(enabled); self._btn_preview_join_v2.setEnabled(enabled)

    class _MergedPreviewDialog(QDialog):
        def __init__(self, panel, qb):
            super().__init__(panel); self.panel = panel; self.qb = qb
            self.setWindowTitle("合并结果预览"); self.resize(1180, 680)
            root = QVBoxLayout(self)
            joins = [j.get("table_name") or j.get("table") or "" for j in qb.joins]
            root.addWidget(QLabel(f"主表：{_table_key(qb.schema_name, qb.table_name)}" + (f"    关联表：{'、'.join(joins)}" if joins else "    关联表：无")))
            tools = QHBoxLayout(); tools.addWidget(QLabel("显示行数:"))
            self.limit = QComboBox(); self.limit.addItems(["10", "20", "50", "100"]); self.limit.setCurrentText("20")
            refresh = QPushButton("刷新"); refresh.clicked.connect(self.refresh)
            tools.addWidget(self.limit); tools.addWidget(refresh); tools.addStretch(1); root.addLayout(tools)
            self.table = QTableWidget(); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setAlternatingRowColors(True); root.addWidget(self.table, 1)
            self.status = QLabel(""); self.status.setStyleSheet("color:#666;"); root.addWidget(self.status)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
            QTimer.singleShot(0, self.refresh)

        def _headers(self, raw):
            sources = _sources(self.panel); expected, counts, table_counts = [], {}, {}
            for src in sources:
                table_counts[src["table"]] = table_counts.get(src["table"], 0) + 1
                for col in src["columns"]:
                    counts[col] = counts.get(col, 0) + 1; expected.append((col, src["database"], src["table"]))
            if len(expected) != len(raw):
                raw_counts, seen, result = {}, {}, []
                for name in raw: raw_counts[name] = raw_counts.get(name, 0) + 1
                for name in raw:
                    seen[name] = seen.get(name, 0) + 1; result.append(name if raw_counts[name] == 1 else f"{name} ({seen[name]})")
                return result
            result = []
            for col, db, table in expected:
                if counts.get(col, 0) == 1: result.append(col)
                else:
                    source = table if table_counts.get(table, 0) == 1 else f"{db}.{table}"
                    result.append(f"{col} ({source})")
            return result

        def refresh(self):
            error = self.qb.validate_joins()
            if error: QMessageBox.warning(self, "关联配置不完整", error); return
            editor = self.panel._editor
            if editor is None: QMessageBox.warning(self, "无法预览", "未找到数据库连接对象。"); return
            cfg = editor._template.db_configs.get("default")
            if cfg is None: QMessageBox.warning(self, "无法预览", "请先配置数据库服务器连接。"); return
            if not editor._db_handler.is_connected("default") and not editor._db_handler.connect(cfg, "default"):
                QMessageBox.critical(self, "连接失败", editor._db_handler.last_error or "数据库连接失败"); return
            sql = self.qb.build_join_preview_sql(int(self.limit.currentText()), cfg.db_type)
            result = editor._db_handler.execute_rows(sql, "default", self.qb.database_name if len(getattr(editor._template, "selected_databases", [])) == 1 else "")
            if result is None: QMessageBox.critical(self, "预览失败", editor._db_handler.last_error or "查询失败"); return
            raw, rows = result; headers = self._headers(raw)
            self.table.clear(); self.table.setColumnCount(len(headers)); self.table.setHorizontalHeaderLabels(headers); self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, value in enumerate(row): self.table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
            self.table.resizeColumnsToContents()
            self.status.setText(f"显示 {len(rows)} 行 | 共 {1 + len(self.qb.joins)} 张表参与关联 | 仅预览 FROM + JOIN，不应用 WHERE/时间条件")

    def _preview_join_result_v2(self):
        qb = self._collect_binding_v2()
        if not qb.table_name: QMessageBox.warning(self, "无法预览", "请先选择主表。"); return
        error = qb.validate_joins()
        if error: QMessageBox.warning(self, "关联配置不完整", error); return
        _MergedPreviewDialog(self, qb).exec()

    def _source_table_changed_v2(self, *_args):
        if getattr(self, "_v2_loading", False): return
        self._refresh_all_join_choices_v2(); self._commit_binding_v2()

    esp.DatabaseBindingPanel.__init__ = panel_init
    esp.DatabaseBindingPanel._clear_filter_rows = _clear_filter_rows_v2
    esp.DatabaseBindingPanel._clear_filter_rows_v2 = _clear_filter_rows_v2
    esp.DatabaseBindingPanel._add_filter_row = _add_filter_row_v2
    esp.DatabaseBindingPanel._add_filter_row_v2 = _add_filter_row_v2
    esp.DatabaseBindingPanel._remove_filter_row_v2 = _remove_filter_row_v2
    esp.DatabaseBindingPanel._join_types_v2 = _join_types_v2
    esp.DatabaseBindingPanel._add_join_condition_v2 = _add_join_condition_v2
    esp.DatabaseBindingPanel._remove_join_condition_v2 = _remove_join_condition_v2
    esp.DatabaseBindingPanel._add_join_row_v2 = _add_join_row_v2
    esp.DatabaseBindingPanel._refresh_join_table_v2 = _refresh_join_table_v2
    esp.DatabaseBindingPanel._refresh_join_row_v2 = _refresh_join_row_v2
    esp.DatabaseBindingPanel._on_join_database_v2 = _on_join_database_v2
    esp.DatabaseBindingPanel._on_join_table_v2 = _on_join_table_v2
    esp.DatabaseBindingPanel._renumber_joins_v2 = _renumber_joins_v2
    esp.DatabaseBindingPanel._move_join_v2 = _move_join_v2
    esp.DatabaseBindingPanel._remove_join_v2 = _remove_join_v2
    esp.DatabaseBindingPanel._clear_joins_v2 = _clear_joins_v2
    esp.DatabaseBindingPanel._refresh_all_join_choices_v2 = _refresh_all_join_choices_v2
    esp.DatabaseBindingPanel._collect_joins_v2 = _collect_joins_v2
    esp.DatabaseBindingPanel._refresh_identifier_choices = _refresh_identifier_choices_v2
    esp.DatabaseBindingPanel._refresh_identifier_choices_v2 = _refresh_identifier_choices_v2
    esp.DatabaseBindingPanel._collect_db_binding = _collect_binding_v2
    esp.DatabaseBindingPanel._collect_binding_v2 = _collect_binding_v2
    esp.DatabaseBindingPanel._commit_binding_v2 = _commit_binding_v2
    esp.DatabaseBindingPanel._on_join_changed_v2 = _on_join_changed_v2
    esp.DatabaseBindingPanel._on_database_finished_v2 = _on_database_finished_v2
    esp.DatabaseBindingPanel._validate_identifiers_v2 = _validate_identifiers_v2
    esp.DatabaseBindingPanel._load_db_binding = _load_binding_v2
    esp.DatabaseBindingPanel._update_db_ui_state = _update_db_ui_state_v2
    esp.DatabaseBindingPanel._update_db_ui_state_v2 = _update_db_ui_state_v2
    esp.DatabaseBindingPanel._preview_join_result_v2 = _preview_join_result_v2
    esp.DatabaseBindingPanel._on_source_table_changed = _source_table_changed_v2
    esp.DatabaseBindingPanel._on_db_config_changed = _commit_binding_v2
    esp.DatabaseBindingPanel._on_optional_query_changed = _commit_binding_v2
