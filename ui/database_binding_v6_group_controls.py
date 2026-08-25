"""最终修正 JOIN 整组控制位置、紧凑布局、控件生命周期与搜索候选关闭行为。"""


def install_database_binding_v6_group_controls():
    import ui.editor_side_panels as esp
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QComboBox, QVBoxLayout

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

    def _force_close_search_popup(combo):
        """选中候选后强制收起，并阻止 FocusIn 延迟逻辑立即把候选重新打开。"""
        if combo is None or not combo.isEditable():
            return
        try:
            combo.hidePopup()
        except RuntimeError:
            return

        completer = combo.completer()
        if completer is None:
            return
        popup = completer.popup()
        if popup is not None:
            popup.hide()

        # V2 的点击/聚焦输入框逻辑会 QTimer.singleShot(0) 再次 complete()。
        # 单纯 hide() 会被这一轮 FocusIn 重新打开，所以选中后短暂摘下 completer。
        # 当前字段联动刷新完成后，再恢复原来的 completer 与候选模型。
        if getattr(combo, "_v6_detached_completer", None) is not None:
            return
        combo._v6_detached_completer = completer
        combo.setCompleter(None)

        def restore(c=combo, saved=completer):
            try:
                if c.completer() is None:
                    c.setCompleter(saved)
                c._v6_detached_completer = None
            except RuntimeError:
                pass

        QTimer.singleShot(150, restore)

    def _ensure_choice_closes(combo):
        """统一所有“可输入 + 可搜索”QComboBox 的选择后关闭行为。"""
        if combo is None or not combo.isEditable():
            return

        # 当前 completer 可能被前面的搜索逻辑重建；每个实际 completer 只接一次。
        comp = combo.completer()
        comp_id = id(comp) if comp is not None else None
        wired_ids = getattr(combo, "_v6_close_wired_ids", set())
        if comp_id in wired_ids:
            return

        def close_now(*_args, c=combo):
            _force_close_search_popup(c)

        # 点击右侧箭头后的普通列表选择。
        if not getattr(combo, "_v6_combo_activated_wired", False):
            combo.activated.connect(close_now)
            combo._v6_combo_activated_wired = True

        # 点击输入框后出现的是 QCompleter popup；鼠标选择和 Enter 都会触发 activated。
        if comp is not None:
            comp.activated.connect(close_now)
            wired_ids.add(comp_id)
            combo._v6_close_wired_ids = wired_ids

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

        _ensure_choice_closes(row.get("left_table_v3"))
        _ensure_choice_closes(row.get("table"))

        for cond in list(row.get("conditions", []) or []):
            _compact_label(cond.get("left_label_v3"), "左表字段:")
            _compact_label(cond.get("right_label_v3"), "右表字段:")
            cond["remove"].setToolTip("删除这一条关联条件")
            widget = cond.get("widget")
            if widget is not None and widget.layout() is not None:
                widget.layout().setContentsMargins(0, 0, 0, 0)
                widget.layout().setSpacing(2)
            _ensure_choice_closes(cond.get("left"))
            _ensure_choice_closes(cond.get("right"))

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

        # row[up/down/remove] 仍是 V2/V3 后续刷新会访问的同一批 QPushButton。
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

        for key in ("v6_up", "v6_down", "v6_remove"):
            row.pop(key, None)

    def _refresh_buttons(panel):
        rows = list(getattr(panel, "_join_rows", []) or [])
        for index, row in enumerate(rows):
            row["up"].setEnabled(index > 0)
            row["down"].setEnabled(index < len(rows) - 1)
            row["remove"].setEnabled(True)

        # 删除到 0 组后必须还能重新添加第一组。
        add_join = getattr(panel, "_btn_add_join_v2", None)
        if add_join is not None and not rows:
            add_join.setEnabled(True)
            add_join.setToolTip("添加第一组表关联")

    def _wire_all_searchable_inputs(panel):
        """数据库绑定区域所有可输入下拉框统一应用选择后关闭规则。"""
        for combo in panel.findChildren(QComboBox):
            if combo.isEditable():
                _ensure_choice_closes(combo)

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
        _wire_all_searchable_inputs(panel)

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
