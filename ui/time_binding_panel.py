"""模板编辑页的单元格时间绑定面板。"""

from copy import deepcopy

from PyQt6.QtCore import QDateTime, Qt, QEvent, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QComboBox,
    QDateTimeEdit, QLabel, QCompleter,
)

from models.time_binding import TimeBinding, TimeRangeType, TimeMode


_RANGE_LABELS = {
    TimeRangeType.DAY: "日",
    TimeRangeType.MONTH: "月",
    TimeRangeType.YEAR: "年",
    TimeRangeType.CUSTOM: "自定义",
    TimeRangeType.FIXED: "固定",
}
_LABEL_TO_RANGE = {v: k for k, v in _RANGE_LABELS.items()}


class _TimeFieldPopupFilter(QObject):
    """时间字段下拉框：点击/聚焦展开，输入时使用本地候选匹配。"""

    def __init__(self, combo, parent=None):
        super().__init__(parent or combo)
        self._combo = combo

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            QTimer.singleShot(0, self._show)
        return False

    def _show(self):
        if self._combo.isEnabled() and self._combo.isVisible():
            self._combo.showPopup()


class _TimeFieldChoiceCloseFilter(QObject):
    """时间字段候选被点击/回车选中后立即收起。"""

    def __init__(self, combo):
        super().__init__(combo)
        self._combo = combo

    def close_popup(self):
        try:
            self._combo.hidePopup()
        except RuntimeError:
            return
        comp = self._combo.completer()
        if comp is not None and comp.popup() is not None:
            comp.popup().hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonRelease:
            QTimer.singleShot(0, self.close_popup)
        elif event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
        ):
            QTimer.singleShot(0, self.close_popup)
        return False


class TimeBindingPanel(QWidget):
    """为模板当前单元格/选区配置时间规则。"""

    time_binding_changed = pyqtSignal()

    def __init__(self, editor, parent=None, undo_manager=None):
        super().__init__(parent)
        self._editor = editor
        self._undo_manager = undo_manager
        self._row = -1
        self._col = -1
        self._selected_cells: list[tuple[int, int]] = []
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        title = QLabel("时间绑定")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        root.addWidget(title)

        hint = QLabel("模板只保存时间规则；具体日期由“报表预览”提供。固定范围除外。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        root.addWidget(hint)

        self._status = QLabel("请选择一个单元格")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "color:#8A5A00; background:#FFF8E1; border:1px solid #F3D98B; "
            "padding:8px; border-radius:4px;"
        )
        root.addWidget(self._status)

        self._config_group = QGroupBox("当前单元格")
        form = QFormLayout(self._config_group)
        self._lbl_cell = QLabel("未选择")
        form.addRow("位置:", self._lbl_cell)

        self._enabled = QCheckBox("启用时间条件")
        self._enabled.stateChanged.connect(self._changed)
        form.addRow(self._enabled)

        # 时间字段也是数据库字段，使用与数据库侧栏一致的可输入下拉框。
        self._time_field = QComboBox()
        self._time_field.setEditable(True)
        self._time_field.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._time_field.lineEdit().setPlaceholderText("选择或输入时间字段")
        completer = self._time_field.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._time_field_filter = _TimeFieldPopupFilter(self._time_field, self._time_field)
        self._time_field.lineEdit().installEventFilter(self._time_field_filter)
        self._time_field.lineEdit().textEdited.connect(
            lambda _text: QTimer.singleShot(
                0,
                lambda: self._time_field.completer().complete()
                if self._time_field.completer() is not None else None,
            )
        )

        # 与数据库绑定区域统一：无论鼠标点击补全候选、按 Enter 选中，都会立即关闭候选层。
        self._time_field_choice_filter = _TimeFieldChoiceCloseFilter(self._time_field)
        if completer is not None:
            completer.activated.connect(
                lambda *_: QTimer.singleShot(0, self._time_field_choice_filter.close_popup)
            )
            popup = completer.popup()
            if popup is not None:
                popup.installEventFilter(self._time_field_choice_filter)
                if popup.viewport() is not None:
                    popup.viewport().installEventFilter(self._time_field_choice_filter)
        self._time_field.activated.connect(
            lambda *_: QTimer.singleShot(0, self._time_field_choice_filter.close_popup)
        )
        self._time_field.lineEdit().returnPressed.connect(
            lambda: QTimer.singleShot(0, self._time_field_choice_filter.close_popup)
        )

        self._time_field.currentTextChanged.connect(self._changed)
        form.addRow("时间字段:", self._time_field)

        self._range_type = QComboBox()
        self._range_type.addItems(["日", "月", "年", "自定义", "固定"])
        self._range_type.currentTextChanged.connect(self._range_changed)
        form.addRow("时间范围:", self._range_type)

        self._mode = QComboBox()
        self._mode.addItems(["预览指定", "当前周期"])
        self._mode.currentIndexChanged.connect(self._changed)
        form.addRow("周期方式:", self._mode)

        self._fixed_start = QDateTimeEdit(QDateTime.currentDateTime())
        self._fixed_start.setCalendarPopup(True)
        self._fixed_start.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._fixed_start.dateTimeChanged.connect(self._changed)
        form.addRow("固定开始:", self._fixed_start)

        self._fixed_end = QDateTimeEdit(QDateTime.currentDateTime())
        self._fixed_end.setCalendarPopup(True)
        self._fixed_end.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._fixed_end.dateTimeChanged.connect(self._changed)
        form.addRow("固定结束:", self._fixed_end)

        root.addWidget(self._config_group)
        root.addStretch(1)
        self._config_group.hide()

    def set_field_choices(self, fields: list[str]):
        """更新缓存字段候选，不访问数据库，并保留当前输入。"""
        current = self._time_field.currentText()
        self._time_field.blockSignals(True)
        self._time_field.clear()
        self._time_field.addItems(list(dict.fromkeys(fields or [])))
        self._time_field.setCurrentText(current)
        self._time_field.blockSignals(False)

        # clear/addItems 后 Qt 可能替换 completer/popup，再次确保新 popup 也安装关闭过滤器。
        completer = self._time_field.completer()
        if completer is not None:
            popup = completer.popup()
            if popup is not None:
                popup.installEventFilter(self._time_field_choice_filter)
                if popup.viewport() is not None:
                    popup.viewport().installEventFilter(self._time_field_choice_filter)

    def set_selected_cells(self, cells: list):
        self._selected_cells = list(dict.fromkeys(cells or []))
        if len(self._selected_cells) > 1:
            self._config_group.setTitle(f"当前选区（{len(self._selected_cells)} 个单元格）")
        else:
            self._config_group.setTitle("当前单元格")

    def set_selection(self, row: int, col: int, _scope: str = "cell"):
        self._row, self._col = row, col
        if row < 0 or col < 0:
            self._lbl_cell.setText("未选择")
            self._config_group.hide()
            self._status.setText("请选择一个单元格")
            self._status.show()
            return
        self._lbl_cell.setText(f"{self._column_name(col)}{row + 1}")
        self._load_current()
        self.refresh_availability()

    def _target_cells(self):
        cells = list(dict.fromkeys(self._selected_cells or []))
        if cells:
            return cells
        if self._row >= 0 and self._col >= 0:
            return [(self._row, self._col)]
        return []

    def refresh_availability(self):
        targets = self._target_cells()
        if not targets:
            self._config_group.hide()
            self._status.setText("请选择一个单元格")
            self._status.show()
            return

        all_enabled = True
        for row, col in targets:
            qb = self._editor._template.get_cell_data(row, col).query_binding
            if qb is None or not qb.enabled:
                all_enabled = False
                break
        if not all_enabled:
            self._config_group.hide()
            self._status.setText("所选单元格中存在未启用数据库绑定的单元格")
            self._status.show()
            return

        self._status.hide()
        self._config_group.show()
        self._update_enabled_state()

    @staticmethod
    def _column_name(col: int) -> str:
        name = ""
        col += 1
        while col:
            col, rem = divmod(col - 1, 26)
            name = chr(65 + rem) + name
        return name

    def _current_query(self):
        if self._row < 0 or self._col < 0:
            return None
        return self._editor._template.get_cell_data(self._row, self._col).query_binding

    def _load_current(self):
        qb = self._current_query()
        self._loading = True
        try:
            binding = qb.time_binding if qb else TimeBinding()
            self._enabled.setChecked(binding.enabled)
            self._time_field.setCurrentText(binding.time_field)
            self._range_type.setCurrentText(_RANGE_LABELS.get(binding.range_type, "日"))
            self._mode.setCurrentIndex(1 if binding.mode == TimeMode.CURRENT else 0)
            if binding.fixed_start:
                dt = QDateTime.fromString(binding.fixed_start, Qt.DateFormat.ISODate)
                if dt.isValid():
                    self._fixed_start.setDateTime(dt)
            if binding.fixed_end:
                dt = QDateTime.fromString(binding.fixed_end, Qt.DateFormat.ISODate)
                if dt.isValid():
                    self._fixed_end.setDateTime(dt)
        finally:
            self._loading = False
        self._update_enabled_state()

    def _range_changed(self, _text: str):
        self._update_enabled_state()
        self._changed()

    def _update_enabled_state(self):
        enabled = self._enabled.isChecked()
        kind = _LABEL_TO_RANGE.get(self._range_type.currentText(), TimeRangeType.DAY)
        self._time_field.setEnabled(enabled)
        self._range_type.setEnabled(enabled)
        self._mode.setEnabled(enabled and kind in (
            TimeRangeType.DAY, TimeRangeType.MONTH, TimeRangeType.YEAR
        ))
        fixed = enabled and kind == TimeRangeType.FIXED
        self._fixed_start.setEnabled(fixed)
        self._fixed_end.setEnabled(fixed)

    def _build_patch_from_sender(self):
        sender = self.sender()
        if sender is self._enabled:
            return {"enabled": self._enabled.isChecked()}
        if sender is self._time_field:
            return {"time_field": self._time_field.currentText().strip()}
        if sender is self._range_type:
            return {
                "range_type": _LABEL_TO_RANGE.get(
                    self._range_type.currentText(), TimeRangeType.DAY
                )
            }
        if sender is self._mode:
            return {
                "mode": TimeMode.CURRENT if self._mode.currentIndex() == 1 else TimeMode.SELECTED
            }
        if sender is self._fixed_start:
            return {
                "fixed_start": self._fixed_start.dateTime().toPyDateTime().isoformat(sep=" ")
            }
        if sender is self._fixed_end:
            return {
                "fixed_end": self._fixed_end.dateTime().toPyDateTime().isoformat(sep=" ")
            }
        return {}

    def _changed(self, *_args):
        if self._loading:
            return
        targets = self._target_cells()
        if not targets:
            return

        for row, col in targets:
            qb = self._editor._template.get_cell_data(row, col).query_binding
            if qb is None or not qb.enabled:
                self.refresh_availability()
                return

        self._update_enabled_state()
        patch = self._build_patch_from_sender()
        if not patch:
            return

        changes = []
        for row, col in targets:
            cd = self._editor._template.get_cell_data(row, col)
            old_dict = cd.to_dict()
            new_cd = type(cd).from_dict(old_dict)
            tb = new_cd.query_binding.time_binding or TimeBinding()
            for key, value in patch.items():
                setattr(tb, key, deepcopy(value))
            new_cd.query_binding.time_binding = tb
            new_dict = new_cd.to_dict()
            if old_dict == new_dict:
                continue
            self._editor._template.set_cell_data(row, col, new_cd)
            changes.append(("cell_data", row, col, old_dict, new_dict))

        if changes and self._undo_manager is not None:
            self._undo_manager.record_batch(changes)
        if changes:
            self.time_binding_changed.emit()
