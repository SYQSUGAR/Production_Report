"""兼容入口：把旧的 editable QComboBox 搜索逻辑切换到 SearchComboBox 架构。

真正实现位于 ``ui.search_combo_box``。本模块只保留旧函数名与一次性的安装接线，
避免历史 V2/V3/V4 再创建实际生效的 QCompleter 或第二层 popup。
"""

from ui.search_combo_box import SearchComboBox, configure_search_combo, set_search_choices


def install_search_combo_architecture():
    """在 WorkspaceWindow 创建前统一接管所有可输入下拉框。"""
    import ui.editor_side_panels as esp
    import ui.join_editor_widget as join_editor
    import ui.time_binding_panel as time_panel

    if getattr(esp, "_search_combo_architecture_installed", False):
        return
    esp._search_combo_architecture_installed = True

    # 新 JOIN / 时间字段从这一刻开始都实例化 SearchComboBox，而不是旧 SearchDropDown。
    join_editor.SearchDropDown = SearchComboBox
    time_panel.SearchDropDown = SearchComboBox

    cls = esp.DatabaseBindingPanel

    # V2 安装时会把类入口替换成 QCompleter 版本；先把“未来新增控件”的配置入口改掉。
    def _configure_identifier_combo(self, combo):
        return configure_search_combo(combo)

    cls._configure_identifier_combo = _configure_identifier_combo
    cls._set_combo_choices = staticmethod(set_search_choices)

    # 但 V2 的 panel_init 内还有闭包直调旧 `_configure_search_combo()`。
    # 所以整个面板构造完成后必须再做一次最终接管，摘掉它刚装上的 QCompleter。
    previous_init = cls.__init__

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        candidates = [
            getattr(self, "_cmb_table", None),
            getattr(self, "_cmb_field", None),
            getattr(self, "_cmb_database", None),
        ]
        for fr in list(getattr(self, "_filter_rows", []) or []):
            candidates.append(fr.get("field_combo"))
        for combo in candidates:
            if combo is not None:
                configure_search_combo(combo)

    cls.__init__ = panel_init

    # V2 的动态 WHERE 行同样在闭包里直调旧搜索逻辑；创建后再统一接管。
    previous_add_filter_v2 = getattr(cls, "_add_filter_row_v2", None)
    if callable(previous_add_filter_v2):
        def add_filter_v2(self, *args, **kwargs):
            result = previous_add_filter_v2(self, *args, **kwargs)
            rows = list(getattr(self, "_filter_rows", []) or [])
            if rows:
                combo = rows[-1].get("field_combo")
                if combo is not None:
                    configure_search_combo(combo)
            return result
        cls._add_filter_row_v2 = add_filter_v2

    # 旧基础面板的 +条件 路径也统一兜底。
    previous_add_filter = getattr(cls, "_add_filter_row", None)
    if callable(previous_add_filter):
        def add_filter(self, *args, **kwargs):
            result = previous_add_filter(self, *args, **kwargs)
            rows = list(getattr(self, "_filter_rows", []) or [])
            if rows:
                combo = rows[-1].get("field_combo")
                if combo is not None:
                    configure_search_combo(combo)
            return result
        cls._add_filter_row = add_filter

    # database_binding_join_rewrite 仍按旧模块名导入这个函数；现在指向新实现。
    globals()["set_search_choices"] = set_search_choices


__all__ = [
    "SearchComboBox",
    "configure_search_combo",
    "set_search_choices",
    "install_search_combo_architecture",
]
