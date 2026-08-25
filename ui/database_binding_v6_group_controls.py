"""最终修正 JOIN 整组控制位置与紧凑布局。"""


def install_database_binding_v6_group_controls():
    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton, QVBoxLayout

    if getattr(esp, "_database_binding_v6_group_controls_installed", False):
        return
    esp._database_binding_v6_group_controls_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2

    def _compact_label(label, text):
        if label is None:
            return
        label.setText(text)
        # 不再人为给标签预留 70~80px；只占文字本身所需宽度，空间尽量留给输入框。
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
            # 卡片内部边距也适当压缩，给表名/字段输入更多横向空间。
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
        controls = row.get("v5_group_controls")
        if controls is None:
            return

        # 旧的整组按钮始终隐藏，右侧控制栏使用独立按钮。
        for old in (row["up"], row["down"], row["remove"]):
            old.hide()

        # V5 的 shell 是“卡片 + 右侧控制栏”。把间距压到最小，让卡片尽量向右延伸。
        shell = row.get("v5_outer_shell")
        if shell is not None and shell.layout() is not None:
            shell.layout().setContentsMargins(0, 0, 0, 0)
            shell.layout().setSpacing(3)

        # 控制栏只保留按钮，不再显示“整组关联”文字。
        controls.setMinimumWidth(32)
        controls.setMaximumWidth(36)
        layout = controls.layout()
        if layout is None:
            layout = QVBoxLayout(controls)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        layout.setContentsMargins(1, 2, 1, 2)
        layout.setSpacing(3)
        layout.addStretch(1)

        btn_up = QPushButton("↑")
        btn_down = QPushButton("↓")
        btn_remove = QPushButton("×")
        for button in (btn_up, btn_down, btn_remove):
            button.setFixedSize(30, 24)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        btn_up.setToolTip("整组关联上移")
        btn_down.setToolTip("整组关联下移")
        btn_remove.setToolTip("删除整组关联")
        btn_up.clicked.connect(lambda: panel._move_join_v2(row, -1))
        btn_down.clicked.connect(lambda: panel._move_join_v2(row, 1))
        btn_remove.clicked.connect(lambda: panel._remove_join_v2(row))

        row["v6_up"] = btn_up
        row["v6_down"] = btn_down
        row["v6_remove"] = btn_remove
        row["v6_external_controls"] = True

    def _refresh_buttons(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        for index, row in enumerate(rows):
            if row.get("v6_up") is not None:
                row["v6_up"].setEnabled(index > 0)
            if row.get("v6_down") is not None:
                row["v6_down"].setEnabled(index < len(rows) - 1)

    def _refresh(panel):
        group = getattr(panel, "_join_group_v2", None)
        if group is not None and group.isCheckable():
            group.blockSignals(True)
            group.setChecked(True)
            group.setCheckable(False)
            group.blockSignals(False)
        for row in list(getattr(panel, "_join_rows", []) or []):
            _rename_and_compact_row(panel, row)
            # 每次刷新都重建右侧控制栏，避免旧 patch 把按钮或标题重新塞回来。
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
    cls._load_db_binding = load_binding
    cls._on_join_changed_v2 = join_changed
