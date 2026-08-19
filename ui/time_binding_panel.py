"""模板编辑页的单元格时间绑定面板。"""

from copy import deepcopy

from PyQt6.QtCore import QDateTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QComboBox,
    QLineEdit, QDateTimeEdit, QLabel,
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


class TimeBindingPanel(QWidget):
    """为模板当前单元格/选区配置时间规则。

    多选时采用与样式、数据库一致的增量修改：改哪个时间属性，就只把
    该属性应用到所有选中单元格，不覆盖其余时间设置。
    """

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

        self._time_field = QLineEdit()
        self._time_field.setPlaceholderText("数据库时间字段，如 record_time")
        self._time_field.textChanged.connect(self._changed)
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
            self._time_field.setText(binding.time_field)
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
            return {"time_field": self._time_field.text().strip()}
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
