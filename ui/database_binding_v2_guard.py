"""V2 数据库绑定在旧控件构造阶段的初始化保护。"""


def install_database_binding_v2_guard():
    import ui.editor_side_panels as esp

    cls = esp.DatabaseBindingPanel
    if getattr(esp, "_database_binding_v2_guard_installed", False):
        return
    esp._database_binding_v2_guard_installed = True

    original_collect = cls._collect_db_binding
    original_update_state = cls._update_db_ui_state
    original_refresh_all = cls._refresh_all_join_choices_v2
    original_renumber = cls._renumber_joins_v2
    original_source_changed = cls._on_source_table_changed
    original_commit = cls._commit_binding_v2

    def ensure_v2_state(self):
        if not hasattr(self, "_join_rows"):
            self._join_rows = []
        if not hasattr(self, "_field_display_lookup"):
            self._field_display_lookup = {}
        if not hasattr(self, "_v2_loading"):
            self._v2_loading = True

    def collect(self):
        ensure_v2_state(self)
        return original_collect(self)

    def update_state(self):
        # StylePanel.__init__ 会在 V2 分区创建前调用一次；这一次直接跳过，
        # panel_init 在新分区插入完成后会再次执行完整状态刷新。
        if not hasattr(self, "_join_group_v2"):
            return
        return original_update_state(self)

    def refresh_all(self):
        ensure_v2_state(self)
        if not hasattr(self, "_joins_layout_v2"):
            return
        return original_refresh_all(self)

    def renumber(self):
        ensure_v2_state(self)
        if not hasattr(self, "_join_group_v2"):
            return
        return original_renumber(self)

    def source_changed(self, *args):
        ensure_v2_state(self)
        if not hasattr(self, "_joins_layout_v2"):
            return
        return original_source_changed(self, *args)

    def commit(self, *args):
        ensure_v2_state(self)
        if not hasattr(self, "_join_group_v2"):
            return
        return original_commit(self, *args)

    cls._collect_db_binding = collect
    cls._update_db_ui_state = update_state
    cls._update_db_ui_state_v2 = update_state
    cls._refresh_all_join_choices_v2 = refresh_all
    cls._renumber_joins_v2 = renumber
    cls._on_source_table_changed = source_changed
    cls._commit_binding_v2 = commit
    cls._on_db_config_changed = commit
    cls._on_optional_query_changed = commit
