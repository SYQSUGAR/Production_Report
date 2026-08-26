"""独立的表关联编辑器。

这套控件不复用旧 DatabaseBindingPanel/V2-V7 的 JOIN QComboBox、QCompleter、row dict
和后装饰布局。JOIN 区域只通过结构化数据与外部数据库绑定面板交互。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QPoint, QSignalBlocker, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class _ChoiceLineEdit(QLineEdit):
    """只有文字显示不完整时才展示完整值提示。"""

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            text = self.text()
            if text and self.fontMetrics().horizontalAdvance(text) > self.contentsRect().width() - 6:
                self.setToolTip(text)
            else:
                self.setToolTip("")
        return super().event(event)


class SearchDropDown(QWidget):
    """只有一层候选 popup 的可输入搜索框。

    - 输入框点击：先完成 QLineEdit 原生光标定位，MouseRelease 后再显示过滤候选。
    - 输入文字：contains / 大小写不敏感过滤。
    - 右侧箭头：同一个 popup 显示完整候选。
    - 点击候选或 Enter：提交唯一真实值后立即关闭 popup。
    - 允许自由文本；不会偷偷改成第一项。

    这里故意不用 editable QComboBox + QCompleter，避免两套 popup、currentIndex 与
    lineEdit 文本相互覆盖。
    """

    valueChanged = pyqtSignal(str)
    textEdited = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._choices: list[str] = []
        self._committed_text = ""
        self._show_all_once = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.edit = _ChoiceLineEdit(self)
        self.edit.setClearButtonEnabled(False)
        lay.addWidget(self.edit, 1)

        self.arrow = QToolButton(self)
        self.arrow.setText("▼")
        self.arrow.setAutoRaise(False)
        self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.arrow.setFixedWidth(22)
        lay.addWidget(self.arrow)

        self.popup = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup_lay = QVBoxLayout(self.popup)
        popup_lay.setContentsMargins(0, 0, 0, 0)
        popup_lay.setSpacing(0)
        self.list = QListWidget(self.popup)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        popup_lay.addWidget(self.list)

        self.edit.installEventFilter(self)
        self.edit.textEdited.connect(self._on_text_edited)
        self.edit.editingFinished.connect(self._on_editing_finished)
        self.arrow.clicked.connect(self.show_all)
        self.list.itemClicked.connect(self._commit_item)
        self.list.itemActivated.connect(self._commit_item)

    def eventFilter(self, watched, event):
        if watched is self.edit:
            if event.type() == QEvent.Type.MouseButtonRelease:
                # MousePress/Release 先完全交给 QLineEdit，使第一次点击即可定位光标。
                QTimer.singleShot(0, self._show_after_mouse_release)
            elif event.type() == QEvent.Type.KeyPress:
                key_event = event
                if isinstance(key_event, QKeyEvent):
                    if key_event.key() == Qt.Key.Key_Down:
                        self.show_filtered()
                        if self.list.count():
                            self.list.setCurrentRow(0)
                            self.list.setFocus()
                        return True
                    if key_event.key() == Qt.Key.Key_Escape and self.popup.isVisible():
                        self.hide_popup()
                        return True
        return super().eventFilter(watched, event)

    def _show_after_mouse_release(self):
        if not self.isEnabled() or not self.isVisible():
            return
        # 拖选/双击选中文字时优先保留编辑动作，不主动弹候选。
        if self.edit.hasSelectedText():
            return
        self.show_filtered()

    def _on_text_edited(self, text: str):
        self.textEdited.emit(text)
        self.show_filtered()

    def _on_editing_finished(self):
        # 点击 popup 项时 QLineEdit 会先失焦，此时不要抢先提交自由文本。
        if self.popup.isVisible():
            return
        text = self.edit.text().strip()
        if text != self._committed_text:
            self._committed_text = text
            self.valueChanged.emit(text)

    def _filtered_choices(self, show_all=False):
        if show_all:
            return list(self._choices)
        text = self.edit.text().strip().casefold()
        if not text:
            return list(self._choices)
        return [item for item in self._choices if text in item.casefold()]

    def _populate_popup(self, show_all=False):
        values = self._filtered_choices(show_all=show_all)
        self.list.clear()
        for value in values:
            item = QListWidgetItem(value)
            item.setToolTip(value)
            self.list.addItem(item)
        return values

    def _show_popup(self, show_all=False):
        if not self.isEnabled() or not self.isVisible():
            return
        values = self._populate_popup(show_all=show_all)
        if not values:
            self.hide_popup()
            return
        width = max(self.width(), 180)
        row_h = max(self.list.sizeHintForRow(0), 22)
        height = min(260, max(28, row_h * min(len(values), 9) + 4))
        self.popup.resize(width, height)
        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        self.popup.move(global_pos)
        self.popup.show()
        self.popup.raise_()
        # popup 出现后仍把输入焦点交给 QLineEdit，保证继续输入/退格自然。
        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_filtered(self):
        self._show_popup(show_all=False)

    def show_all(self):
        self._show_popup(show_all=True)

    def hide_popup(self):
        self.popup.hide()

    def _commit_item(self, item):
        if item is None:
            return
        self._commit_text(item.text())

    def _commit_text(self, text: str, emit=True):
        text = str(text or "").strip()
        with QSignalBlocker(self.edit):
            self.edit.setText(text)
        self._committed_text = text
        self.hide_popup()
        # 点击候选后明确把焦点还给输入框，但不重新弹 popup。
        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.edit.setCursorPosition(len(text))
        if emit:
            self.valueChanged.emit(text)

    def set_choices(self, choices, preserve=True):
        values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
        current = self.edit.text() if preserve else ""
        self._choices = values
        if not preserve:
            self.setCurrentText("", emit=False)
        elif current:
            with QSignalBlocker(self.edit):
                self.edit.setText(current)
        if self.popup.isVisible():
            self.show_filtered()

    def choices(self):
        return list(self._choices)

    def currentText(self):
        return self.edit.text().strip()

    def setCurrentText(self, text, emit=False):
        self._commit_text(str(text or ""), emit=emit)

    def setPlaceholderText(self, text):
        self.edit.setPlaceholderText(text)


class JoinConditionRow(QWidget):
    changed = pyqtSignal()
    removeRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_lookup: dict[str, str] = {}
        self.right_lookup: dict[str, str] = {}

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.connector = QComboBox(self)
        self.connector.addItems(["AND", "OR"])
        self.connector.setFixedWidth(58)
        lay.addWidget(self.connector)

        self.left_label = QLabel("左表字段:", self)
        lay.addWidget(self.left_label)
        self.left = SearchDropDown(self)
        self.left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.left, 1)

        eq = QLabel("=", self)
        eq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(eq)

        self.right_label = QLabel("右表字段:", self)
        lay.addWidget(self.right_label)
        self.right = SearchDropDown(self)
        self.right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.right, 1)

        self.remove = QPushButton("×", self)
        self.remove.setFixedSize(28, 24)
        self.remove.setToolTip("删除这一条关联条件")
        lay.addWidget(self.remove)

        self.connector.currentTextChanged.connect(lambda *_: self.changed.emit())
        self.left.valueChanged.connect(lambda *_: self.changed.emit())
        self.right.valueChanged.connect(lambda *_: self.changed.emit())
        self.remove.clicked.connect(lambda: self.removeRequested.emit(self))

    def set_first(self, first: bool):
        self.connector.setVisible(not first)
        if first:
            self.connector.setCurrentText("AND")

    def set_field_choices(self, left_choices, left_lookup, right_choices, right_lookup):
        self.left_lookup = dict(left_lookup or {})
        self.right_lookup = dict(right_lookup or {})
        self.left.set_choices(left_choices, preserve=True)
        self.right.set_choices(right_choices, preserve=True)

    def is_complete(self):
        return bool(self.left.currentText() and self.right.currentText())

    def load_data(self, data: dict, first: bool):
        self.set_first(first)
        self.connector.setCurrentText(str(data.get("connector", "AND")).upper())
        left = str(data.get("left", "") or "")
        right = str(data.get("right", "") or "")
        self.left.setCurrentText(left.rsplit(".", 1)[-1] if left else "", emit=False)
        self.right.setCurrentText(right.rsplit(".", 1)[-1] if right else "", emit=False)

    def to_dict(self):
        left_text = self.left.currentText()
        right_text = self.right.currentText()
        return {
            "left": self.left_lookup.get(left_text, left_text),
            "op": "=",
            "right": self.right_lookup.get(right_text, right_text),
            "connector": self.connector.currentText().upper() or "AND",
        }


class JoinCard(QWidget):
    changed = pyqtSignal(object)
    moveRequested = pyqtSignal(object, int)
    removeRequested = pyqtSignal(object)

    def __init__(self, join_types, parent=None):
        super().__init__(parent)
        self.index = 0
        self.conditions: list[JoinConditionRow] = []

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(3)

        self.frame = QFrame(self)
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        shell.addWidget(self.frame, 1)
        root = QVBoxLayout(self.frame)
        root.setContentsMargins(3, 4, 3, 4)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(4)
        self.number = QLabel("1.", self.frame)
        self.number.setMinimumWidth(18)
        top.addWidget(self.number)
        self.join_type = QComboBox(self.frame)
        self.join_type.addItems(list(join_types))
        self.join_type.setMaximumWidth(120)
        top.addWidget(self.join_type)
        top.addStretch(1)
        root.addLayout(top)

        table_row = QHBoxLayout()
        table_row.setSpacing(2)
        self.left_name_label = QLabel("左表名:", self.frame)
        table_row.addWidget(self.left_name_label)
        self.left_table = SearchDropDown(self.frame)
        table_row.addWidget(self.left_table, 1)
        self.left_result = QLabel("当前合并结果", self.frame)
        self.left_result.setStyleSheet("color:#555;")
        self.left_result.hide()
        table_row.addWidget(self.left_result, 1)
        self.right_name_label = QLabel("右表名:", self.frame)
        table_row.addWidget(self.right_name_label)
        self.right_table = SearchDropDown(self.frame)
        table_row.addWidget(self.right_table, 1)
        root.addLayout(table_row)

        self.conditions_box = QWidget(self.frame)
        self.conditions_layout = QVBoxLayout(self.conditions_box)
        self.conditions_layout.setContentsMargins(0, 0, 0, 0)
        self.conditions_layout.setSpacing(3)
        root.addWidget(self.conditions_box)

        self.add_condition = QPushButton("+ 条件", self.frame)
        self.add_condition.setMaximumWidth(82)
        root.addWidget(self.add_condition, 0, Qt.AlignmentFlag.AlignLeft)

        controls = QWidget(self)
        controls.setFixedWidth(32)
        ctrl = QVBoxLayout(controls)
        ctrl.setContentsMargins(1, 2, 1, 2)
        ctrl.setSpacing(3)
        ctrl.addStretch(1)
        self.up = QPushButton("↑", controls)
        self.down = QPushButton("↓", controls)
        self.remove = QPushButton("×", controls)
        for button in (self.up, self.down, self.remove):
            button.setFixedSize(30, 24)
            ctrl.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        ctrl.addStretch(1)
        shell.addWidget(controls)

        self.up.setToolTip("整组关联上移")
        self.down.setToolTip("整组关联下移")
        self.remove.setToolTip("删除整组关联")

        self.join_type.currentTextChanged.connect(lambda *_: self.changed.emit(self))
        self.left_table.valueChanged.connect(lambda *_: self.changed.emit(self))
        self.right_table.valueChanged.connect(lambda *_: self.changed.emit(self))
        self.add_condition.clicked.connect(self._add_condition_clicked)
        self.up.clicked.connect(lambda: self.moveRequested.emit(self, -1))
        self.down.clicked.connect(lambda: self.moveRequested.emit(self, 1))
        self.remove.clicked.connect(lambda: self.removeRequested.emit(self))

        self.add_condition_row()

    def set_index(self, index: int, count: int, source_text: str):
        self.index = index
        self.number.setText(f"{index + 1}.")
        first = index == 0
        self.left_name_label.setText("左表名:" if first else "左侧结果:")
        self.left_table.setVisible(first)
        self.left_result.setVisible(not first)
        if first:
            if source_text and self.left_table.currentText() != source_text:
                self.left_table.setCurrentText(source_text, emit=False)
        self.up.setEnabled(index > 0)
        self.down.setEnabled(index < count - 1)
        for idx, cond in enumerate(self.conditions):
            cond.set_first(idx == 0)

    def set_table_choices(self, choices):
        self.left_table.set_choices(choices, preserve=True)
        self.right_table.set_choices(choices, preserve=True)

    def add_condition_row(self, data=None):
        cond = JoinConditionRow(self.conditions_box)
        self.conditions.append(cond)
        self.conditions_layout.addWidget(cond)
        cond.changed.connect(lambda: self.changed.emit(self))
        cond.removeRequested.connect(self._remove_condition)
        if data:
            cond.load_data(data, len(self.conditions) == 1)
        self._refresh_condition_state()
        return cond

    def _add_condition_clicked(self):
        if self.conditions and not self.conditions[-1].is_complete():
            self._refresh_condition_state()
            return
        self.add_condition_row()
        self.changed.emit(self)

    def _remove_condition(self, cond):
        if cond not in self.conditions:
            return
        self.conditions.remove(cond)
        cond.setParent(None)
        cond.deleteLater()
        if not self.conditions:
            self.add_condition_row()
        self._refresh_condition_state()
        self.changed.emit(self)

    def _refresh_condition_state(self):
        for idx, cond in enumerate(self.conditions):
            cond.set_first(idx == 0)
        ready = bool(self.conditions) and self.conditions[-1].is_complete()
        self.add_condition.setEnabled(ready)
        self.add_condition.setToolTip(
            "添加一条 AND / OR 关联条件" if ready else "当前关联条件填写完整后可继续添加条件"
        )

    def is_complete(self):
        source_ok = self.left_table.currentText() if self.index == 0 else True
        return bool(
            source_ok
            and self.right_table.currentText()
            and self.conditions
            and all(cond.is_complete() for cond in self.conditions)
        )


@dataclass
class SourceRef:
    database: str
    table: str
    alias: str
    columns: list[str]


class JoinEditorWidget(QGroupBox):
    """最终版 JOIN 编辑器；不依赖旧 `_join_rows`。"""

    changed = pyqtSignal()
    fieldsChanged = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__("表关联 JOIN（0）", parent)
        self.cards: list[JoinCard] = []
        self.metadata: dict[str, dict[str, list[str]]] = {}
        self.selected_databases: list[str] = []
        self.table_lookup: dict[str, tuple[str, str]] = {}
        self.table_reverse: dict[tuple[str, str], str] = {}
        self.source_text = ""
        self.db_type = "mysql"
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 6)
        root.setSpacing(6)
        help_label = QLabel("用于将多张数据表按照字段关系组合。", self)
        help_label.setStyleSheet("color:#777; font-size:11px;")
        root.addWidget(help_label)

        self.cards_box = QWidget(self)
        self.cards_layout = QVBoxLayout(self.cards_box)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        root.addWidget(self.cards_box)

        self.add_join = QPushButton("+ 添加关联", self)
        self.add_join.clicked.connect(self._add_join_clicked)
        root.addWidget(self.add_join)
        self._refresh_add_join_state()

    def _join_types(self):
        values = ["LEFT JOIN", "INNER JOIN", "RIGHT JOIN"]
        if self.db_type.lower() == "sqlserver":
            values.append("FULL JOIN")
        return values

    def set_metadata(self, metadata, selected_databases, db_type="mysql"):
        self.metadata = metadata or {}
        self.selected_databases = list(selected_databases or [])
        self.db_type = (db_type or "mysql").lower()
        self._build_table_lookup()
        choices = list(self.table_lookup.keys())
        for card in self.cards:
            card.set_table_choices(choices)
        self._refresh_all(emit=False)

    def _build_table_lookup(self):
        counts: dict[str, int] = {}
        for db in self.selected_databases:
            for table in (self.metadata.get(db, {}) or {}):
                counts[table] = counts.get(table, 0) + 1
        lookup = {}
        reverse = {}
        for db in self.selected_databases:
            for table in sorted((self.metadata.get(db, {}) or {}).keys(), key=str.lower):
                display = f"{table} ({db})" if counts.get(table, 0) > 1 else table
                lookup[display] = (db, table)
                reverse[(db, table)] = display
        self.table_lookup = lookup
        self.table_reverse = reverse

    def table_choices(self):
        return list(self.table_lookup.keys())

    def resolve_table(self, text: str):
        text = str(text or "").strip()
        if not text:
            return "", ""
        if text in self.table_lookup:
            return self.table_lookup[text]
        matches = []
        for db in self.selected_databases:
            if text in (self.metadata.get(db, {}) or {}):
                matches.append((db, text))
        return matches[0] if len(matches) == 1 else ("", "")

    def display_table(self, database: str, table: str):
        return self.table_reverse.get((database, table), table or "")

    def columns(self, database: str, table: str):
        return list(((self.metadata.get(database, {}) or {}).get(table, []) or []))

    def _new_card(self, data=None):
        card = JoinCard(self._join_types(), self.cards_box)
        self.cards.append(card)
        self.cards_layout.addWidget(card)
        card.changed.connect(self._card_changed)
        card.moveRequested.connect(self._move_card)
        card.removeRequested.connect(self._remove_card)
        card.set_table_choices(self.table_choices())
        if data:
            card.join_type.setCurrentText(str(data.get("type", "LEFT JOIN")))
            db = str(data.get("database_name", "") or "")
            table = str(data.get("table_name", data.get("table", "")) or "")
            if db and table.startswith(db + "."):
                table = table[len(db) + 1 :]
            card.right_table.setCurrentText(self.display_table(db, table), emit=False)
            # constructor 已有一条空条件，加载旧配置时先清掉再按实际数量创建。
            for cond in list(card.conditions):
                card.conditions.remove(cond)
                cond.setParent(None)
                cond.deleteLater()
            conditions = list(data.get("conditions") or [])
            if not conditions and data.get("on"):
                # legacy on 无法可靠拆解时保留一条待编辑条件。
                conditions = [{}]
            for item in conditions or [{}]:
                card.add_condition_row(item)
        return card

    def _add_join_clicked(self):
        if self.cards and not self.cards[-1].is_complete():
            self._refresh_add_join_state()
            return
        self._new_card()
        self._refresh_all(emit=True)

    def _remove_card(self, card):
        if card not in self.cards:
            return
        self.cards.remove(card)
        self.cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._refresh_all(emit=True)

    def _move_card(self, card, delta):
        if card not in self.cards:
            return
        old = self.cards.index(card)
        new = old + int(delta)
        if new < 0 or new >= len(self.cards):
            return
        # source table 属于整个关联链，不随第一个卡片移动。
        if self.cards:
            first_source = self.cards[0].left_table.currentText().strip()
            if first_source:
                self.source_text = first_source
        self.cards.pop(old)
        self.cards.insert(new, card)
        self.cards_layout.removeWidget(card)
        self.cards_layout.insertWidget(new, card)
        self._refresh_all(emit=True)

    def _card_changed(self, card):
        if self._loading:
            return
        if card in self.cards and self.cards.index(card) == 0:
            text = card.left_table.currentText().strip()
            if text:
                self.source_text = text
        self._refresh_all(emit=True)

    def _sources_before(self, card_index: int):
        result: list[SourceRef] = []
        if self.cards:
            source_text = self.cards[0].left_table.currentText().strip() or self.source_text
        else:
            source_text = self.source_text
        db, table = self.resolve_table(source_text)
        if table:
            result.append(SourceRef(db, table, "t1", self.columns(db, table)))
        for idx, card in enumerate(self.cards[:card_index]):
            rdb, rtable = self.resolve_table(card.right_table.currentText())
            if rtable:
                result.append(SourceRef(rdb, rtable, f"t{idx + 2}", self.columns(rdb, rtable)))
        return result

    def _refresh_card_fields(self, index: int, card: JoinCard):
        left_sources = self._sources_before(index)
        left_choices = []
        left_lookup = {}
        for src in left_sources:
            for column in src.columns:
                if column not in left_lookup:
                    # JOIN 区域按用户要求只展示裸字段名；重名时按合并顺序取第一个来源。
                    left_choices.append(column)
                    left_lookup[column] = f"{src.alias}.{column}"

        rdb, rtable = self.resolve_table(card.right_table.currentText())
        right_columns = self.columns(rdb, rtable) if rtable else []
        alias = f"t{index + 2}"
        right_lookup = {column: f"{alias}.{column}" for column in right_columns}
        for cond in card.conditions:
            cond.set_field_choices(left_choices, left_lookup, right_columns, right_lookup)
        card._refresh_condition_state()

    def _refresh_all(self, emit: bool):
        choices = self.table_choices()
        count = len(self.cards)
        if self.cards:
            current_source = self.cards[0].left_table.currentText().strip()
            if current_source:
                self.source_text = current_source
        for idx, card in enumerate(self.cards):
            card.set_table_choices(choices)
            card.set_index(idx, count, self.source_text)
            self._refresh_card_fields(idx, card)
        self.setTitle(f"表关联 JOIN（{count}）")
        self._refresh_add_join_state()
        fields, lookup = self.merged_fields()
        self.fieldsChanged.emit(fields, lookup)
        if emit and not self._loading:
            self.changed.emit()

    def _refresh_add_join_state(self):
        ready = not self.cards or self.cards[-1].is_complete()
        self.add_join.setEnabled(ready)
        self.add_join.setToolTip(
            "添加第一组表关联" if not self.cards else (
                "继续关联下一张表" if ready else "当前关联填写完整后可继续添加关联"
            )
        )

    def clear(self):
        self._loading = True
        try:
            for card in list(self.cards):
                self.cards_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()
            self.cards = []
            self.source_text = ""
        finally:
            self._loading = False
        self._refresh_all(emit=False)

    def load_binding(self, binding):
        self._loading = True
        try:
            for card in list(self.cards):
                self.cards_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()
            self.cards = []
            db = str(getattr(binding, "database_name", "") or "")
            table = str(getattr(binding, "table_name", "") or "")
            self.source_text = self.display_table(db, table)
            joins = list(getattr(binding, "joins", []) or [])
            for item in joins:
                self._new_card(item)
            if self.cards:
                self.cards[0].left_table.setCurrentText(self.source_text, emit=False)
        finally:
            self._loading = False
        self._refresh_all(emit=False)

    def binding_parts(self, through_count=None):
        cards = self.cards if through_count is None else self.cards[: max(0, int(through_count))]
        source_text = self.cards[0].left_table.currentText().strip() if self.cards else self.source_text
        sdb, stable = self.resolve_table(source_text)
        joins = []
        for idx, card in enumerate(cards):
            rdb, rtable = self.resolve_table(card.right_table.currentText())
            conditions = [cond.to_dict() for cond in card.conditions]
            joins.append({
                "type": card.join_type.currentText() or "LEFT JOIN",
                "database_name": rdb,
                "schema_name": "",
                "table_name": rtable,
                "alias": f"t{idx + 2}",
                "conditions": conditions,
            })
        return {
            "database_name": sdb,
            "schema_name": "",
            "table_name": stable,
            "source_alias": "t1" if cards else "",
            "joins": joins,
        }

    def pair_count(self):
        return len(self.cards)

    def pair_label(self, index: int):
        if index < 0 or index >= len(self.cards):
            return ""
        card = self.cards[index]
        left = card.left_table.currentText().strip() if index == 0 else "当前合并结果"
        right = card.right_table.currentText().strip()
        return f"第{index + 1}对：{left or '未选择'} ↔ {right or '未选择'}"

    def pair_complete(self, index: int):
        if index < 0 or index >= len(self.cards):
            return False
        return self.cards[index].is_complete()

    def chain_complete(self, through_index: int):
        if through_index < 0:
            return True
        if through_index >= len(self.cards):
            return False
        return all(card.is_complete() for card in self.cards[: through_index + 1])

    def merged_fields(self):
        sources = self._sources_before(len(self.cards))
        # 把最后一张右表也纳入候选。
        if self.cards:
            idx = len(self.cards) - 1
            rdb, rtable = self.resolve_table(self.cards[-1].right_table.currentText())
            if rtable:
                sources.append(SourceRef(rdb, rtable, f"t{idx + 2}", self.columns(rdb, rtable)))

        counts = {}
        table_counts = {}
        for src in sources:
            table_counts[src.table] = table_counts.get(src.table, 0) + 1
            for col in src.columns:
                counts[col] = counts.get(col, 0) + 1

        choices = []
        lookup = {}
        for src in sources:
            for col in src.columns:
                if counts.get(col, 0) == 1:
                    display = col
                else:
                    source_name = src.table
                    if table_counts.get(src.table, 0) > 1:
                        source_name = f"{src.database}.{src.table}"
                    display = f"{col} ({source_name})"
                if display in lookup:
                    display = f"{col} ({src.database}.{src.table})"
                lookup[display] = f"{src.alias}.{col}" if len(sources) > 1 else col
                choices.append(display)
        return choices, lookup
