"""数据库绑定 V2 的折叠分区与数量显示。"""


def install_database_binding_v2_finish():
    import ui.editor_side_panels as esp

    if getattr(esp, "_database_binding_v2_finish_installed", False):
        return
    esp._database_binding_v2_finish_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_commit = cls._commit_binding_v2
    previous_add_filter = cls._add_filter_row_v2
    previous_remove_filter = cls._remove_filter_row_v2

    def _set_group_contents_visible(group, visible):
        layout = group.layout()
        if layout is None:
            return
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(visible)

    def _refresh_filter_title(self):
        count = 0
        for row in getattr(self, "_filter_rows", []):
            field = row.get("field_combo")
            value = row.get("value")
            if ((field is not None and field.currentText().strip()) or
                    (value is not None and value.text().strip())):
                count += 1
        if hasattr(self, "_filter_group_v2"):
            self._filter_group_v2.setTitle(f"数据筛选 WHERE（{count}）")

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        for group in (self._join_group_v2, self._filter_group_v2):
            group.setCheckable(True)
            group.setChecked(True)
            group.toggled.connect(lambda checked, g=group: _set_group_contents_visible(g, checked))
        _refresh_filter_title(self)

    def commit(self, *args):
        result = previous_commit(self, *args)
        _refresh_filter_title(self)
        return result

    def add_filter(self):
        result = previous_add_filter(self)
        _refresh_filter_title(self)
        return result

    def remove_filter(self, record):
        result = previous_remove_filter(self, record)
        _refresh_filter_title(self)
        return result

    cls.__init__ = panel_init
    cls._commit_binding_v2 = commit
    cls._on_db_config_changed = commit
    cls._on_optional_query_changed = commit
    cls._add_filter_row_v2 = add_filter
    cls._add_filter_row = add_filter
    cls._remove_filter_row_v2 = remove_filter
    cls._refresh_filter_title_v2 = _refresh_filter_title
