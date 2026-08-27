"""兼容入口：把旧的 editable QComboBox 搜索逻辑切换到 SearchComboBox 架构。

真正实现位于 ``ui.search_combo_box``。本模块只保留旧函数名，避免历史 V2/V3/V4
继续创建 QCompleter 或第二层 popup。
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
    # 旧类仍可被历史模块 import，但运行时不再用于创建新控件。
    join_editor.SearchDropDown = SearchComboBox
    time_panel.SearchDropDown = SearchComboBox

    cls = esp.DatabaseBindingPanel

    # V2 安装时会把这里替换成 QCompleter 版本；现在统一改回单 popup 行为。
    def _configure_identifier_combo(self, combo):
        return configure_search_combo(combo)

    cls._configure_identifier_combo = _configure_identifier_combo
    cls._set_combo_choices = staticmethod(set_search_choices)

    # database_binding_join_rewrite 仍按旧模块名导入 set_search_choices；这里已经是新实现。
    globals()["set_search_choices"] = set_search_choices


__all__ = [
    "SearchComboBox",
    "configure_search_combo",
    "set_search_choices",
    "install_search_combo_architecture",
]
