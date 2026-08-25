"""最终修正 JOIN 整组控制位置、紧凑布局与控件生命周期。"""


def install_database_binding_v6_group_controls():
    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout

    if getattr(esp, "_database_binding_v6_group_controls_installed", False):
        return
    esp._database_binding_v6_group_controls_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_remove_join = cls._remove_join_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2

    def _compact_label(label, text):
        if label is None:
            return
        label.setText(text)
        # 标签只占文字实际宽度，横向空间尽量留给表名和字段输入框。
        label.setMinimumWidth(0)
        label.setMaximumWidth(label.sizeHint().width() + 2)

    def _rename_and_compact_row(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return
        index = rows.index(row)

        _compact_label(
            row.get("left_label_v3"),
            "左表名:" if index == 0 else "左侧结果:",
        )
        _compact_label(row.get("right_label_v3"), "右表名:")

        table_line = row.get("table_line_v3")
        if table_line is not None and table_line.layout() is not None:
            table_line.layout().setContentsMargins(0, 0, 0, 0)
            table_line.layout().setSpacing(2)

        frame = row.get("widget")
        if frame is not None and frame.layout() is not None:
            frame.layout().setContentsMargins(3, 4, 3, 4)
            frame.layout().setSpacing(3)

        for cond in list(row.get("conditions", []) or []):
            _compact_label(cond.get("left_label_v3"), "左表字段:")
            _compact_label(cond.get("right_label_v3"), "右表字段:")
            cond["remove"].setToolTip("删除这一条关联条件")
            widget = cond.get("widget")
            if widget is not None and widget.layout() is not None:
                widget.layout().setContentsMargins(0, 0, 0, 0)
                widget.layout().setSpacing(2)

    def _install_external_controls(panel, row):
        """复用 V2 原始 ↑ ↓ ×，只移动位置，绝不销毁按钮对象。"""
        controls = row.get("v5_group_controls")
        if controls is None:
            return

        shell = row.get("v5_outer_shell")
        if shell is not None and shell.layout() is not None:
            shell.layout().setContentsMargins(0, 0, 0, 0)
            shell.layout().setSpacing(3)

        controls.setMinimumWidth(32)
        controls.setMaximumWidth(36)
        layout = controls.layout()
        if layout is None:
            layout = QVBoxLayout(controls)

        original_buttons = (row["up"], row["down"], row["remove"])

        # 清理 V5/V6 旧版遗留的标题或替代按钮，但保留真正的 row 按钮。
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if widget in original_buttons:
                widget.setParent(controls)
                continue
            widget.setParent(None)
            widget.deleteLater()

        layout.setContentsMargins(1, 2, 1, 2)
        layout.setSpacing(3)
        layout.addStretch(1)

        # 关键：row[up/down/remove] 仍是 V2/V3 后续刷新会访问的同一批 QPushButton。
        # 不创建替代按钮，也不 deleteLater，因此不会再出现 wrapped C/C++ object deleted。
        for button in original_buttons:
            button.setParent(controls)
            button.show()
            button.setFixedSize(30, 24)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        row["up"].setToolTip("整组关联上移")
        row["down"].setToolTip("整组关联下移")
        row["remove"].setToolTip("删除整组关联")
        row["v6_external_controls"] = True

        # 清理旧版 V6 创建过的替代按钮引用，避免后续状态更新碰到已销毁对象。
        for key in ("v6_up", "v6_down", "v6_remove"):
            row.pop(key, None)

    def _refresh_buttons(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        for index, row in enumerate(rows):
            # V3 自己也会更新这两个状态，这里再次同步，且直接使用原始按钮。
            row["up"].setEnabled(index > 0)
            row["down"].setEnabled(index < len(rows) - 1)
            # 删除按钮任何一组都可用，包括第一组和最后一组。
            row["remove"].setEnabled(True)

        # 删除到 0 组后必须还能重新添加第一组，不能把用户锁死在空状态。
        add_join = getattr(panel, "_btn_add_join_v2", None)
        if add_join is not None and not rows:
            add_join.setEnabled(True)
            add_join.setToolTip("添加第一组表关联")

    def _refresh(panel):
        group = getattr(panel, "_join_group_v2", None)
        if group is not None and group.isCheckable():
            group.blockSignals(True)
            group.setChecked(True)
            group.setCheckable(False)
            group.blockSignals(False)
        for row in list(getattr(panel, "_join_rows", []) or []):
            _rename_and_compact_row(panel, row)
            _install_external_controls(panel, row)
        _refresh_buttons(panel)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        _refresh(self)

    def add_join(self, data=None):
        result = previous_add_join(self, data)
        _refresh(self)
        return result

    def add_condition(self, row, data=None):
        result = previous_add_condition(self, row, data)
        _refresh(self)
        return result

    def remove_join(self, row):
        # 明确允许删除任意整组关联，包括第 1 组以及仅剩的最后 1 组。
        if row not in list(getattr(self, "_join_rows", []) or []):
            return
        result = previous_remove_join(self, row)
        _refresh(self)
        return result

    def load_binding(self):
        result = previous_load(self)
        _refresh(self)
        return result

    def join_changed(self, *args):
        result = previous_join_changed(self, *args)
        _refresh(self)
        return result

    cls.__init__ = panel_init
    cls._add_join_row_v2 = add_join
    cls._add_join_condition_v2 = add_condition
    cls._remove_join_v2 = remove_join
    cls._load_db_binding = load_binding
    cls._on_join_changed_v2 = join_changed
