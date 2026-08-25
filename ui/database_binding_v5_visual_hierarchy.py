"""数据库绑定视觉层级收尾：取消 JOIN 复选框、外置整组控制、统一左右命名。"""


def install_database_binding_v5_visual_hierarchy():
    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

    if getattr(esp, "_database_binding_v5_visual_hierarchy_installed", False):
        return
    esp._database_binding_v5_visual_hierarchy_installed = True
    cls = esp.DatabaseBindingPanel

    previous_init = cls.__init__
    previous_add_join = cls._add_join_row_v2
    previous_add_condition = cls._add_join_condition_v2
    previous_load = cls._load_db_binding
    previous_join_changed = cls._on_join_changed_v2

    def _show_group_contents(group):
        layout = group.layout()
        if layout is None:
            return
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.show()

    def _remove_join_group_checkbox(panel):
        group = getattr(panel, "_join_group_v2", None)
        if group is None:
            return
        # V2 finish 曾把 QGroupBox 设为 checkable，标题左侧因此出现了复选框。
        # 表关联模式已经由“单表 / 表关联”控制，这里不再保留第二层开关。
        if group.isCheckable():
            group.blockSignals(True)
            group.setChecked(True)
            group.setCheckable(False)
            group.blockSignals(False)
        _show_group_contents(group)

    def _rename_condition(cond):
        left_label = cond.get("left_label_v3")
        right_label = cond.get("right_label_v3")
        if left_label is not None:
            left_label.setText("左表字段:")
            left_label.setMinimumWidth(72)
        if right_label is not None:
            right_label.setText("右表字段:")
            right_label.setMinimumWidth(72)
        cond["remove"].setToolTip("删除这一条关联条件")

    def _rename_row(panel, row):
        rows = list(getattr(panel, "_join_rows", []) or [])
        if row not in rows:
            return
        index = rows.index(row)
        left_label = row.get("left_label_v3")
        right_label = row.get("right_label_v3")
        if index == 0:
            if left_label is not None:
                left_label.setText("左表名:")
                left_label.setMinimumWidth(72)
            if row.get("left_table_v3") is not None:
                row["left_table_v3"].show()
        else:
            # 第二组起左侧是上一轮合并结果，不伪装成一个实际物理表名。
            if left_label is not None:
                left_label.setText("左侧结果:")
                left_label.setMinimumWidth(72)
            if row.get("left_table_v3") is not None:
                row["left_table_v3"].hide()
        if right_label is not None:
            right_label.setText("右表名:")
            right_label.setMinimumWidth(72)
        for cond in list(row.get("conditions", []) or []):
            _rename_condition(cond)

    def _externalize_group_controls(panel, row):
        """把 ↑ ↓ × 从关联卡片内部真正移到卡片右侧独立控制区。"""
        if row.get("v5_outer_shell") is not None:
            return
        joins_layout = getattr(panel, "_joins_layout_v2", None)
        frame = row.get("widget")
        if joins_layout is None or frame is None:
            return

        insert_at = joins_layout.indexOf(frame)
        if insert_at < 0:
            insert_at = joins_layout.count()

        # 无论 V4 把按钮放在标题行哪里，都先从卡片内部布局移除。
        top_item = frame.layout().itemAt(0) if frame.layout() is not None else None
        top_layout = top_item.layout() if top_item is not None else None
        if top_layout is not None:
            for button in (row["up"], row["down"], row["remove"]):
                top_layout.removeWidget(button)

        joins_layout.removeWidget(frame)

        shell = QWidget(getattr(panel, "_joins_container_v2", panel))
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(8)
        shell_layout.addWidget(frame, 1)

        controls = QWidget(shell)
        controls.setMinimumWidth(48)
        controls.setMaximumWidth(62)
        controls.setToolTip("以下按钮操作整组表关联")
        control_layout = QVBoxLayout(controls)
        control_layout.setContentsMargins(4, 6, 4, 6)
        control_layout.setSpacing(4)
        title = QLabel("整组\n关联")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#666; font-size:10px;")
        control_layout.addWidget(title)
        control_layout.addStretch(1)
        for button in (row["up"], row["down"], row["remove"]):
            button.setParent(controls)
            button.setFixedWidth(32)
            control_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        control_layout.addStretch(1)
        row["up"].setToolTip("整组关联上移")
        row["down"].setToolTip("整组关联下移")
        row["remove"].setToolTip("删除整组关联")

        shell_layout.addWidget(controls, 0)
        joins_layout.insertWidget(insert_at, shell)
        row["v5_outer_shell"] = shell
        row["v5_group_controls"] = controls

    def _refresh_visuals(panel):
        _remove_join_group_checkbox(panel)
        for row in list(getattr(panel, "_join_rows", []) or []):
            _externalize_group_controls(panel, row)
            _rename_row(panel, row)

    def panel_init(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        _refresh_visuals(self)

    def add_join(self, data=None):
        result = previous_add_join(self, data)
        _refresh_visuals(self)
        return result

    def add_condition(self, row, data=None):
        result = previous_add_condition(self, row, data)
        _refresh_visuals(self)
        return result

    def move_join(self, row, delta):
        rows = list(getattr(self, "_join_rows", []) or [])
        if row not in rows:
            return
        old = rows.index(row)
        new = old + delta
        if new < 0 or new >= len(rows):
            return
        self._join_rows.pop(old)
        self._join_rows.insert(new, row)
        shell = row.get("v5_outer_shell") or row["widget"]
        self._joins_layout_v2.removeWidget(shell)
        self._joins_layout_v2.insertWidget(new, shell)
        self._renumber_joins_v2()
        self._refresh_all_join_choices_v2()
        self._on_join_changed_v2()
        _refresh_visuals(self)

    def remove_join(self, row):
        if row not in getattr(self, "_join_rows", []):
            return
        self._join_rows.remove(row)
        shell = row.get("v5_outer_shell")
        if shell is not None:
            self._joins_layout_v2.removeWidget(shell)
            shell.setParent(None)
            shell.deleteLater()
        else:
            row["widget"].setParent(None)
            row["widget"].deleteLater()
        self._renumber_joins_v2()
        self._refresh_all_join_choices_v2()
        self._on_join_changed_v2()
        _refresh_visuals(self)

    def clear_joins(self):
        for row in list(getattr(self, "_join_rows", []) or []):
            shell = row.get("v5_outer_shell")
            target = shell or row.get("widget")
            if target is not None:
                target.setParent(None)
                target.deleteLater()
        self._join_rows = []
        self._renumber_joins_v2()
        _remove_join_group_checkbox(self)

    def load_binding(self):
        result = previous_load(self)
        _refresh_visuals(self)
        return result

    def join_changed(self, *args):
        result = previous_join_changed(self, *args)
        _refresh_visuals(self)
        return result

    cls.__init__ = panel_init
    cls._add_join_row_v2 = add_join
    cls._add_join_condition_v2 = add_condition
    cls._move_join_v2 = move_join
    cls._remove_join_v2 = remove_join
    cls._clear_joins_v2 = clear_joins
    cls._load_db_binding = load_binding
    cls._on_join_changed_v2 = join_changed
