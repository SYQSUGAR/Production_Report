"""服务器级数据库连接、多数据库范围选择与元数据缓存扩展。"""


def install_db_connection_patch():
    import ui.main_window as mw
    import ui.editor_side_panels as esp
    import ui.report_preview_page as rpp
    from models.template_model import TemplateModel
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QApplication, QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout,
        QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget,
    )

    if getattr(mw, "_db_connection_patch_installed", False):
        return
    mw._db_connection_patch_installed = True

    # ------------------------------------------------------------------
    # TemplateModel：保存“本项目启用数据库”范围。
    # ------------------------------------------------------------------
    original_template_init = TemplateModel.__init__
    original_template_to_dict = TemplateModel.to_dict
    original_template_from_dict = TemplateModel.from_dict

    def template_init(self, *args, **kwargs):
        original_template_init(self, *args, **kwargs)
        self.selected_databases = []

    def template_to_dict(self):
        data = original_template_to_dict(self)
        data["selected_databases"] = list(getattr(self, "selected_databases", []))
        return data

    def template_from_dict(cls, data):
        model = original_template_from_dict(data)
        selected = list(data.get("selected_databases", []) or [])
        # 旧模板迁移：原先 database 写在连接配置中时，自动作为唯一已选库。
        if not selected:
            legacy = model.db_configs.get("default")
            legacy_db = (getattr(legacy, "database", "") or "").strip() if legacy else ""
            if legacy_db:
                selected = [legacy_db]
        model.selected_databases = selected
        for config in model.db_configs.values():
            setattr(config, "_selected_databases", list(selected))
        return model

    TemplateModel.__init__ = template_init
    TemplateModel.to_dict = template_to_dict
    TemplateModel.from_dict = classmethod(template_from_dict)

    # ------------------------------------------------------------------
    # 数据库连接：建立服务器连接后，单库项目自动切换到该默认库。
    # ------------------------------------------------------------------
    original_connect = mw.DbHandler.connect

    def activate_selected_database(handler, config_key, selected):
        if len(selected) != 1:
            return
        conn = handler._connections.get(config_key)
        config = handler._configs.get(config_key)
        if not conn or not config:
            return
        database = selected[0]
        try:
            if config.db_type == "mysql":
                conn.select_db(database)
            else:
                safe = database.replace("]", "]]" )
                cursor = conn.cursor()
                try:
                    cursor.execute(f"USE [{safe}]")
                finally:
                    cursor.close()
        except Exception as exc:
            handler.last_error = str(exc)

    def connect(self, config, config_key="default"):
        ok = original_connect(self, config, config_key)
        if ok:
            activate_selected_database(
                self, config_key, list(getattr(config, "_selected_databases", []) or [])
            )
        return ok

    mw.DbHandler.connect = connect

    # ------------------------------------------------------------------
    # 服务器连接配置窗口：不再要求数据库名，并回显已保存配置。
    # ------------------------------------------------------------------
    original_dialog_init = mw._DbConfigDialog.__init__
    original_dialog_get_config = mw._DbConfigDialog.get_config

    def dialog_init(self, parent=None):
        original_dialog_init(self, parent)
        # 数据库名改由“本项目数据库管理”选择。
        label = self.layout().labelForField(self._txt_database)
        if label is not None:
            label.hide()
        self._txt_database.hide()
        self._txt_database.setText("")

        template = getattr(parent, "_template", None)
        config = template.db_configs.get("default") if template is not None else None
        if config is None:
            return
        idx = self._cmb_type.findText(config.db_type)
        if idx >= 0:
            self._cmb_type.setCurrentIndex(idx)
        self._txt_host.setText(config.host)
        self._spn_port.setValue(int(config.port))
        self._txt_user.setText(config.user)
        self._txt_password.setText(config.password)
        self._txt_charset.setText(config.charset)

    def dialog_get_config(self):
        config = original_dialog_get_config(self)
        config.database = ""
        return config

    mw._DbConfigDialog.__init__ = dialog_init
    mw._DbConfigDialog.get_config = dialog_get_config

    def connection_signature(config):
        if config is None:
            return None
        return (
            config.db_type, config.host, int(config.port), config.user, config.charset,
        )

    def clear_metadata_cache(editor):
        editor._database_metadata_cache = {}
        editor._database_metadata_signature = None
        top = editor.window()
        panel = getattr(top, "_db_panel", None)
        if panel is not None:
            panel.clear_database_metadata()

    def db_config(self):
        old = self._template.db_configs.get("default")
        dlg = mw._DbConfigDialog(self)
        if dlg.exec() == mw.QDialog.DialogCode.Accepted:
            config = dlg.get_config()
            changed_server = connection_signature(old) != connection_signature(config)
            self._db_handler.disconnect("default")
            if changed_server:
                self._template.selected_databases = []
                clear_metadata_cache(self)
            setattr(config, "_selected_databases", list(self._template.selected_databases))
            self._template.db_configs["default"] = config
            self._save_session()
            self._status_label.setText("数据库服务器配置已保存")

    mw.MainWindow._db_config = db_config

    def db_test_connect(self):
        config = self._template.db_configs.get("default")
        if not config:
            QMessageBox.warning(self, "提示", "请先配置数据库服务器连接")
            return
        setattr(config, "_selected_databases", list(getattr(self._template, "selected_databases", [])))
        success = self._db_handler.connect(config, "default")
        if success:
            QMessageBox.information(self, "连接成功", "数据库服务器连接测试通过")
        else:
            detail = getattr(self._db_handler, "last_error", "") or "未知错误"
            QMessageBox.critical(self, "连接失败", f"数据库服务器连接失败。\n\n详细错误：\n{detail}")

    mw.MainWindow._db_test_connect = db_test_connect

    # ------------------------------------------------------------------
    # 元数据统一缓存：selected database -> table -> all columns。
    # ------------------------------------------------------------------
    def ensure_server_connection(editor):
        config = editor._template.db_configs.get("default")
        if not config:
            return False
        setattr(config, "_selected_databases", list(getattr(editor._template, "selected_databases", [])))
        if editor._db_handler.is_connected("default"):
            return True
        return editor._db_handler.connect(config, "default")

    def metadata_signature(editor):
        config = editor._template.db_configs.get("default")
        return (
            connection_signature(config),
            tuple(getattr(editor._template, "selected_databases", []) or []),
        )

    def load_project_metadata(editor, force=False):
        selected = list(getattr(editor._template, "selected_databases", []) or [])
        if not selected:
            editor._database_metadata_cache = {}
            editor._database_metadata_signature = metadata_signature(editor)
            return {}
        sig = metadata_signature(editor)
        if not force and getattr(editor, "_database_metadata_signature", None) == sig:
            return getattr(editor, "_database_metadata_cache", {}) or {}
        if not ensure_server_connection(editor):
            return {}
        cache = editor._db_handler.get_multi_schema_metadata(selected, "default")
        editor._database_metadata_cache = cache or {}
        editor._database_metadata_signature = sig
        activate_selected_database(editor._db_handler, "default", selected)
        return editor._database_metadata_cache

    def get_db_metadata(self, config_key="default"):
        return load_project_metadata(self, force=False)

    mw.MainWindow._get_db_metadata = get_db_metadata

    # ------------------------------------------------------------------
    # 数据库范围双列表选择器。
    # ------------------------------------------------------------------
    class DatabaseScopeDialog(QDialog):
        def __init__(self, editor):
            super().__init__(editor)
            self._editor = editor
            self._dirty = False
            self.setWindowTitle("本项目数据库管理")
            self.resize(720, 470)

            root = QVBoxLayout(self)
            search_row = QHBoxLayout()
            search_row.addWidget(QLabel("搜索数据库:"))
            self._search = QLineEdit()
            self._search.setPlaceholderText("输入数据库名称，同时筛选左右列表")
            self._search.textChanged.connect(self._refresh_lists)
            search_row.addWidget(self._search, 1)
            root.addLayout(search_row)

            middle = QHBoxLayout()
            left_box = QVBoxLayout()
            left_box.addWidget(QLabel("待添加数据库"))
            self._available = QListWidget()
            self._available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            left_box.addWidget(self._available, 1)
            middle.addLayout(left_box, 1)

            actions = QVBoxLayout()
            actions.addStretch(1)
            self._btn_add = QPushButton("→")
            self._btn_remove = QPushButton("←")
            self._btn_add_all = QPushButton("全部→")
            self._btn_remove_all = QPushButton("←全部")
            for button in (self._btn_add, self._btn_remove, self._btn_add_all, self._btn_remove_all):
                button.setMinimumWidth(80)
                actions.addWidget(button)
            actions.addStretch(1)
            middle.addLayout(actions)

            right_box = QVBoxLayout()
            right_box.addWidget(QLabel("已添加数据库（本项目使用范围）"))
            self._selected = QListWidget()
            self._selected.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            right_box.addWidget(self._selected, 1)
            middle.addLayout(right_box, 1)
            root.addLayout(middle, 1)

            buttons = QDialogButtonBox()
            self._ok = buttons.addButton("确定", QDialogButtonBox.ButtonRole.AcceptRole)
            self._cancel = buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
            self._ok.clicked.connect(self._save_and_accept)
            self._cancel.clicked.connect(self._cancel_requested)
            root.addWidget(buttons)

            self._btn_add.clicked.connect(self._add_selected)
            self._btn_remove.clicked.connect(self._remove_selected)
            self._btn_add_all.clicked.connect(self._add_all)
            self._btn_remove_all.clicked.connect(self._remove_all)

            if not ensure_server_connection(editor):
                self._server_databases = []
            else:
                self._server_databases = editor._db_handler.list_databases("default")
            existing = list(getattr(editor._template, "selected_databases", []) or [])
            # 已保存但暂时不可见的库仍保留在右侧，便于用户主动移除。
            self._selected_names = list(dict.fromkeys(existing))
            self._refresh_lists()

        def _available_names(self):
            selected = set(self._selected_names)
            return [name for name in self._server_databases if name not in selected]

        def _refresh_lists(self):
            text = self._search.text().strip().lower()
            self._available.clear()
            self._selected.clear()
            for name in sorted(self._available_names(), key=str.lower):
                if not text or text in name.lower():
                    self._available.addItem(name)
            for name in self._selected_names:
                if not text or text in name.lower():
                    self._selected.addItem(name)

        @staticmethod
        def _names_from_selection(widget):
            return [item.text() for item in widget.selectedItems()]

        def _mark_dirty(self):
            self._dirty = True

        def _add_selected(self):
            names = self._names_from_selection(self._available)
            if not names:
                return
            for name in names:
                if name not in self._selected_names:
                    self._selected_names.append(name)
            self._mark_dirty(); self._refresh_lists()

        def _remove_selected(self):
            names = set(self._names_from_selection(self._selected))
            if not names:
                return
            self._selected_names = [name for name in self._selected_names if name not in names]
            self._mark_dirty(); self._refresh_lists()

        def _add_all(self):
            for name in self._server_databases:
                if name not in self._selected_names:
                    self._selected_names.append(name)
            self._mark_dirty(); self._refresh_lists()

        def _remove_all(self):
            if self._selected_names:
                self._selected_names = []
                self._mark_dirty(); self._refresh_lists()

        def _commit(self):
            self._editor._template.selected_databases = list(self._selected_names)
            config = self._editor._template.db_configs.get("default")
            if config is not None:
                config.database = ""
                setattr(config, "_selected_databases", list(self._selected_names))
            self._editor._database_metadata_signature = None
            cache = load_project_metadata(self._editor, force=True)
            self._editor._save_session()
            top = self._editor.window()
            panel = getattr(top, "_db_panel", None)
            if panel is not None:
                panel.refresh_database_metadata()
            if self._selected_names:
                table_count = sum(len(tables) for tables in cache.values())
                column_count = sum(len(cols) for tables in cache.values() for cols in tables.values())
                self._editor._status_label.setText(
                    f"已保存 {len(self._selected_names)} 个数据库，读取 {table_count} 张表、{column_count} 个字段"
                )
            else:
                self._editor._status_label.setText("本项目未选择数据库")
            self._dirty = False

        def _save_and_accept(self):
            self._commit()
            super().accept()

        def _confirm_unsaved(self):
            if not self._dirty:
                return "discard"
            box = QMessageBox(self)
            box.setWindowTitle("未保存的数据库选择")
            box.setText("当前数据库选择尚未保存。")
            save_btn = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
            discard_btn = box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is save_btn:
                return "save"
            if clicked is discard_btn:
                return "discard"
            if clicked is cancel_btn:
                return "cancel"
            return "cancel"

        def _cancel_requested(self):
            action = self._confirm_unsaved()
            if action == "save":
                self._commit(); super().accept()
            elif action == "discard":
                super().reject()

        def closeEvent(self, event):
            action = self._confirm_unsaved()
            if action == "cancel":
                event.ignore(); return
            if action == "save":
                self._commit()
            event.accept()

    def db_scope_manage(self):
        config = self._template.db_configs.get("default")
        if not config:
            QMessageBox.warning(self, "提示", "请先完成“数据库服务器连接配置”。")
            return
        setattr(config, "_selected_databases", list(getattr(self._template, "selected_databases", [])))
        if not self._db_handler.is_connected("default") and not self._db_handler.connect(config, "default"):
            detail = self._db_handler.last_error or "未知错误"
            QMessageBox.critical(self, "连接失败", f"无法读取服务器数据库列表。\n\n{detail}")
            return
        DatabaseScopeDialog(self).exec()

    mw.MainWindow._db_scope_manage = db_scope_manage

    original_setup_menu = mw.MainWindow._setup_menu

    def setup_menu(self):
        original_setup_menu(self)
        db_menu = None
        for action in self.menuBar().actions():
            menu = action.menu()
            if menu and menu.title().replace("&", "").startswith("数据库"):
                db_menu = menu; break
        if db_menu is None:
            return
        actions = db_menu.actions()
        for action in actions:
            if action.text().startswith("数据库连接配置"):
                action.setText("数据库服务器连接配置...")
        scope_action = QAction("本项目数据库管理...", self)
        scope_action.triggered.connect(self._db_scope_manage)
        insert_before = actions[1] if len(actions) > 1 else None
        if insert_before is not None:
            db_menu.insertAction(insert_before, scope_action)
        else:
            db_menu.addAction(scope_action)
        self._act_database_scope = scope_action

    mw.MainWindow._setup_menu = setup_menu

    # ------------------------------------------------------------------
    # 右侧数据库绑定面板：Database -> Table -> Column。
    # ------------------------------------------------------------------
    original_panel_init = esp.DatabaseBindingPanel.__init__
    original_refresh_template = esp.DatabaseBindingPanel.refresh_template
    original_collect_binding = esp.DatabaseBindingPanel._collect_db_binding
    original_load_binding = esp.DatabaseBindingPanel._load_db_binding
    original_clear_metadata = esp.DatabaseBindingPanel.clear_database_metadata

    def panel_init(self, *args, **kwargs):
        original_panel_init(self, *args, **kwargs)
        self._all_db_metadata = {}
        self._join_table_lookup = {}
        row = QWidget(self._builder_widget)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("数据库:"))
        from PyQt6.QtWidgets import QComboBox
        self._cmb_database = QComboBox()
        self._cmb_database.setEditable(False)
        row_layout.addWidget(self._cmb_database, 1)
        self._builder_widget.layout().insertWidget(1, row)
        self._cmb_database.currentTextChanged.connect(self._on_project_database_changed)
        self._populate_project_databases()

    def panel_db_signature(self, template=None):
        template = template or self._template
        cfg = template.db_configs.get("default") if template else None
        if cfg is None:
            return None
        return (
            cfg.db_type, cfg.host, cfg.port, cfg.user, cfg.charset,
            tuple(getattr(template, "selected_databases", []) or []),
        )

    def populate_project_databases(self, preferred=""):
        selected = list(getattr(self._template, "selected_databases", []) or [])
        current = preferred or (self._cmb_database.currentText() if self._cmb_database.count() else "")
        self._cmb_database.blockSignals(True)
        self._cmb_database.clear()
        self._cmb_database.addItems(selected)
        if current in selected:
            self._cmb_database.setCurrentText(current)
        elif selected:
            self._cmb_database.setCurrentIndex(0)
        self._cmb_database.blockSignals(False)

    def make_join_choices(self):
        counts = {}
        for tables in self._all_db_metadata.values():
            for table in tables:
                counts[table] = counts.get(table, 0) + 1
        lookup = {}
        choices = []
        for database in getattr(self._template, "selected_databases", []) or []:
            for table in sorted(self._all_db_metadata.get(database, {}), key=str.lower):
                display = f"{table} ({database})" if counts.get(table, 0) > 1 else table
                # 如果无同名但名称偶然冲突，退化为带库名显示。
                if display in lookup:
                    display = f"{table} ({database})"
                lookup[display] = (database, table)
                choices.append(display)
        self._join_table_lookup = lookup
        return choices

    def apply_project_database(self, database):
        self._db_metadata = dict(self._all_db_metadata.get(database, {}) or {})
        tables = sorted(self._db_metadata, key=str.lower)
        self._set_combo_choices(self._cmb_table, tables)
        self._set_combo_choices(self._cmb_join_table, self._make_join_choices())
        self._refresh_identifier_choices()

    def refresh_database_metadata(self):
        provider = self._metadata_provider
        metadata = provider("default") if provider else {}
        selected = list(getattr(self._template, "selected_databases", []) or [])
        # 兼容旧 provider 返回 {table:[columns]}。
        if metadata and all(isinstance(value, list) for value in metadata.values()):
            database = selected[0] if selected else ""
            metadata = {database: metadata}
        self._all_db_metadata = metadata or {}
        self._metadata_config_signature = self._db_config_signature()
        self._populate_project_databases()
        database = self._cmb_database.currentText().strip()
        self._apply_project_database(database)
        table_count = sum(len(tables) for tables in self._all_db_metadata.values())
        column_count = sum(len(columns) for tables in self._all_db_metadata.values() for columns in tables.values())
        if table_count:
            self._lbl_metadata_state.setText(
                f"数据库已读取：{len(selected)} 个库，{table_count} 张表，{column_count} 个字段"
            )
            self._lbl_metadata_state.setStyleSheet("color:#287A3D;")
            return True
        self._set_metadata_unread_state()
        return False

    def clear_database_metadata(self):
        self._all_db_metadata = {}
        self._join_table_lookup = {}
        original_clear_metadata(self)
        if hasattr(self, "_cmb_database"):
            self._populate_project_databases()

    def refresh_template(self, template):
        original_refresh_template(self, template)
        if hasattr(self, "_cmb_database"):
            self._populate_project_databases()

    def refresh_identifier_choices(self, _text=""):
        database = self._cmb_database.currentText().strip() if hasattr(self, "_cmb_database") else ""
        source_parts = self._cmb_table.currentText().strip().split()
        source = source_parts[0] if source_parts else ""
        source_columns = self._all_db_metadata.get(database, {}).get(source, [])

        join_display = self._cmb_join_table.currentText().strip()
        join_db, join_table = self._join_table_lookup.get(join_display, (database, join_display))
        joined_columns = self._all_db_metadata.get(join_db, {}).get(join_table, [])

        source_alias = source_parts[-1] if source_parts else source
        join_alias = join_table.split()[-1] if join_table else ""
        self._set_combo_choices(self._cmb_field, list(source_columns))
        qualified_source = [f"{source_alias}.{name}" for name in source_columns]
        qualified_join = [f"{join_alias}.{name}" for name in joined_columns]
        all_qualified = qualified_source + qualified_join
        self._set_combo_choices(self._cmb_join_left, qualified_source)
        self._set_combo_choices(self._cmb_join_right, qualified_join)
        for row in self._filter_rows:
            self._set_combo_choices(row["field_combo"], all_qualified or list(source_columns))

    def on_project_database_changed(self, database):
        if self._suppress_update:
            return
        self._apply_project_database(database)
        selected = list(getattr(self._template, "selected_databases", []) or [])
        self._apply_db_patch({
            "database_name": database,
            "schema_name": "",
            "qualify_database": len(selected) > 1,
        })

    def collect_binding(self):
        qb = original_collect_binding(self)
        database = self._cmb_database.currentText().strip() if hasattr(self, "_cmb_database") else ""
        selected = list(getattr(self._template, "selected_databases", []) or [])
        qb.database_name = database
        qb.schema_name = ""
        qb.qualify_database = len(selected) > 1
        if qb.joins:
            join_display = self._cmb_join_table.currentText().strip()
            join_db, join_table = self._join_table_lookup.get(join_display, (database, join_display))
            if join_table:
                if len(selected) > 1 or (join_db and join_db != database):
                    qb.joins[0]["table"] = f"{join_db}.{join_table}" if join_db else join_table
                else:
                    qb.joins[0]["table"] = join_table
                qb.joins[0]["database_name"] = join_db
        return qb

    def load_binding(self):
        original_load_binding(self)
        if self._current_row < 0 or self._current_col < 0:
            return
        qb = self._template.get_cell_data(self._current_row, self._current_col).query_binding
        preferred = qb.database_name if qb else ""
        if not preferred:
            selected = list(getattr(self._template, "selected_databases", []) or [])
            preferred = selected[0] if selected else ""
        self._populate_project_databases(preferred)
        self._apply_project_database(self._cmb_database.currentText().strip())
        if qb:
            self._cmb_table.setCurrentText(qb.table_name)
            self._cmb_field.setCurrentText(qb.field_name)
        self._update_sql_preview()

    esp.DatabaseBindingPanel.__init__ = panel_init
    esp.DatabaseBindingPanel._db_config_signature = panel_db_signature
    esp.DatabaseBindingPanel._populate_project_databases = populate_project_databases
    esp.DatabaseBindingPanel._make_join_choices = make_join_choices
    esp.DatabaseBindingPanel._apply_project_database = apply_project_database
    esp.DatabaseBindingPanel.refresh_database_metadata = refresh_database_metadata
    esp.DatabaseBindingPanel.clear_database_metadata = clear_database_metadata
    esp.DatabaseBindingPanel.refresh_template = refresh_template
    esp.DatabaseBindingPanel._refresh_identifier_choices = refresh_identifier_choices
    esp.DatabaseBindingPanel._on_project_database_changed = on_project_database_changed
    esp.DatabaseBindingPanel._collect_db_binding = collect_binding
    esp.DatabaseBindingPanel._load_db_binding = load_binding

    # ------------------------------------------------------------------
    # 报表生成连接：恢复模板后也保证单库默认库生效。
    # ------------------------------------------------------------------
    original_preview_ensure = rpp.ReportPreviewPage._ensure_db_connection

    def preview_ensure(self, config_key):
        config = self._source_template.db_configs.get(config_key)
        if config is None and config_key == "default":
            config = self._source_template.db_configs.get("default")
        if config is not None:
            setattr(config, "_selected_databases", list(getattr(self._source_template, "selected_databases", []) or []))
        ok = original_preview_ensure(self, config_key)
        if ok:
            activate_selected_database(
                self._editor._db_handler,
                config_key,
                list(getattr(self._source_template, "selected_databases", []) or []),
            )
        return ok

    rpp.ReportPreviewPage._ensure_db_connection = preview_ensure
