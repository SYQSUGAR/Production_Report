"""最终修正 JOIN 整组控制位置与左右标签命名。"""


def install_database_binding_v6_group_controls():
    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout

    if getattr(esp, "_database_binding_v6_group_controls_installed", False):
        return
    esp._database_binding_v6_group_controls_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2

    def _rename_row(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return
        index = rows.index(row)

        left_label = row.get("left_label_v3")
        right_label = row.get("right_label_v3")
        if left_label is not None:
            if index == 0:
                left_label.setText("左表名:")
            else:
                left_label.setText("左侧结果:")
            left_label.setMinimumWidth(76)
        if right_label is not None:
            right_label.setText("右表名:")
            right_label.setMinimumWidth(76)

        for cond in list(row.get("conditions", []) or []):
            left_field_label = cond.get("left_label_v3")
            right_field_label = cond.get("right_label_v3")
            if left_field_label is not None:
                left_field_label.setText("左表字段:")
                left_field_label.setMinimumWidth(82)
            if right_field_label is not None:
                right_field_label.setText("右表字段:")
                right_field_label.setMinimumWidth(82)
            cond["remove"].setToolTip("删除这一条关联条件")

    def _install_external_controls(panel, row):
        controls = row.get("v5_group_controls")
        if controls is None or row.get("v6_external_controls"):
            return
        row["v6_external_controls"] = True

        # 旧的整组按钮不再参与布局，避免被前面版本重新放回卡片顶部。
        for old in (row["up"], row["down"], row["remove"]):
            old.hide()

        layout = controls.layout()
        if layout is None:
            layout = QVBoxLayout(controls)
        # 清掉旧控制区内容（旧版只有“整组关联”文字和可能被抢走的按钮）。
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(5)

        title = QLabel("整组\n关联")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#666; font-size:10px;")
        layout.addWidget(title)
        layout.addStretch(1)

        btn_up = QPushButton("↑")
        btn_down = QPushButton("↓")
        btn_remove = QPushButton("×")
        for button in (btn_up, btn_down, btn_remove):
            button.setFixedSize(32, 26)
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
            _rename_row(panel, row)
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
