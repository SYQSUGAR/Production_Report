"""统一的可输入搜索下拉框。

整个程序的下拉控件只保留两类：
- QComboBox：不可输入，只从固定候选中选择；
- SearchComboBox(QComboBox)：可输入、可搜索、允许自由文本。

SearchComboBox 只使用 QComboBox 自己的 popup，不使用 QCompleter 第二层弹窗。
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QSignalBlocker, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox


class _SearchComboBehavior(QObject):
    """给 editable QComboBox 提供统一的单-popup搜索行为。"""

    valueCommitted = pyqtSignal(str)
    textEdited = pyqtSignal(str)

    def __init__(self, combo: QComboBox):
        super().__init__(combo)
        self.combo = combo
        self._choices: list[str] = []
        self._committed_text = ""
        self._updating = False
        self._committing = False
        self._pending_filter_text: str | None = None

        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # 关键：彻底关闭 editable QComboBox 自动附带的 QCompleter。
        # 搜索候选始终只显示 QComboBox 自己的 popup。
        combo.setCompleter(None)

        edit = combo.lineEdit()
        if edit is not None:
            edit.installEventFilter(self)
            edit.textEdited.connect(self._on_text_edited)
            edit.editingFinished.connect(self._on_editing_finished)
        combo.installEventFilter(self)
        combo.activated.connect(self._on_activated)

        self._choices = [combo.itemText(i) for i in range(combo.count())]
        self._committed_text = combo.currentText().strip()

    def eventFilter(self, watched, event):
        combo = self.combo
        edit = combo.lineEdit()

        if watched is edit:
            if event.type() == QEvent.Type.MouseButtonRelease:
                # QLineEdit 先处理本次点击，下一轮事件循环才展开候选。
                QTimer.singleShot(0, self._show_after_mouse_release)
            elif event.type() == QEvent.Type.ToolTip:
                text = edit.text() if edit is not None else ""
                if text and edit.fontMetrics().horizontalAdvance(text) > edit.contentsRect().width() - 8:
                    edit.setToolTip(text)
                else:
                    edit.setToolTip("")
            return False

        if watched is combo and event.type() == QEvent.Type.MouseButtonPress:
            # 点击原生箭头时先恢复完整候选，再交给 QComboBox 自己展开。
            try:
                opt = QStyleOptionComboBox()
                combo.initStyleOption(opt)
                arrow_rect = combo.style().subControlRect(
                    QStyle.ComplexControl.CC_ComboBox,
                    opt,
                    QStyle.SubControl.SC_ComboBoxArrow,
                    combo,
                )
                if arrow_rect.contains(event.position().toPoint()):
                    self._apply_visible_choices(self._choices, combo.currentText(), restore_edit_state=True)
            except Exception:
                pass
            return False

        return False

    def _show_after_mouse_release(self):
        combo = self.combo
        edit = combo.lineEdit()
        if self._committing or self._updating:
            return
        if not combo.isEnabled() or not combo.isVisible() or edit is None:
            return
        # 拖选、双击选字形成选区时，优先保留文字编辑，不主动弹候选。
        if edit.hasSelectedText():
            return
        self.show_filtered()

    def _filtered_choices(self, text: str):
        key = str(text or "").strip().casefold()
        if not key:
            return list(self._choices)
        return [value for value in self._choices if key in value.casefold()]

    def _on_text_edited(self, text: str):
        if self._updating or self._committing:
            return
        self.textEdited.emit(text)
        self._pending_filter_text = str(text)
        QTimer.singleShot(0, self._apply_pending_filter)

    def _apply_pending_filter(self):
        if self._pending_filter_text is None or self._committing:
            return
        edit = self.combo.lineEdit()
        if edit is None:
            return
        text = edit.text()
        self._pending_filter_text = None
        self.show_filtered(text)

    def show_filtered(self, text: str | None = None):
        combo = self.combo
        edit = combo.lineEdit()
        if self._committing or self._updating:
            return
        if not combo.isEnabled() or not combo.isVisible() or edit is None:
            return
        current = edit.text() if text is None else str(text)
        values = self._filtered_choices(current)
        self._apply_visible_choices(values, current, restore_edit_state=True)
        if not values:
            combo.hidePopup()
            return
        # 只打开 QComboBox 自己的 popup，没有第二层 QCompleter。
        QComboBox.showPopup(combo)
        QTimer.singleShot(0, self._restore_edit_focus)

    def show_all(self):
        combo = self.combo
        current = combo.currentText()
        self._apply_visible_choices(self._choices, current, restore_edit_state=True)
        QComboBox.showPopup(combo)

    def _restore_edit_focus(self):
        edit = self.combo.lineEdit()
        if edit is not None and self.combo.isVisible():
            edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _apply_visible_choices(self, values, current_text: str, restore_edit_state=True):
        combo = self.combo
        edit = combo.lineEdit()
        if edit is None:
            return

        cursor = edit.cursorPosition()
        sel_start = edit.selectionStart()
        selected_len = len(edit.selectedText())
        text = str(current_text or "")

        self._updating = True
        try:
            with QSignalBlocker(combo), QSignalBlocker(edit):
                combo.clear()
                combo.addItems(list(values))
                idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
                combo.setCurrentIndex(idx if idx >= 0 else -1)
                combo.setEditText(text)
                if restore_edit_state:
                    edit.setCursorPosition(min(cursor, len(text)))
                    if sel_start >= 0 and selected_len > 0:
                        start = min(sel_start, len(text))
                        edit.setSelection(start, min(selected_len, max(0, len(text) - start)))
        finally:
            self._updating = False

    def _on_activated(self, index: int):
        if self._updating:
            return
        combo = self.combo
        text = combo.itemText(index).strip() if 0 <= index < combo.count() else combo.currentText().strip()
        self.commit_text(text, emit=True)

    def _on_editing_finished(self):
        if self._updating or self._committing:
            return
        try:
            if self.combo.view().isVisible():
                return
        except Exception:
            pass
        text = self.combo.currentText().strip()
        if text != self._committed_text:
            self.commit_text(text, emit=True)

    def commit_text(self, text: str, emit=True):
        combo = self.combo
        edit = combo.lineEdit()
        if edit is None:
            return
        text = str(text or "").strip()
        self._committing = True
        try:
            # 提交后恢复完整候选；自由文本没有匹配项时保持 index=-1。
            self._apply_visible_choices(self._choices, text, restore_edit_state=False)
            idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
            with QSignalBlocker(combo), QSignalBlocker(edit):
                combo.setCurrentIndex(idx if idx >= 0 else -1)
                combo.setEditText(text)
                edit.setCursorPosition(len(text))
            combo.hidePopup()
            self._committed_text = text
        finally:
            self._committing = False
        if emit:
            self.valueCommitted.emit(text)

    def set_choices(self, choices, preserve=True, current=None):
        values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
        combo = self.combo
        text = combo.currentText() if current is None else str(current)
        if not preserve and current is None:
            text = ""
        self._choices = values
        combo._search_choices = list(values)
        self._apply_visible_choices(values, text, restore_edit_state=False)
        self._committed_text = text.strip()

    def choices(self):
        return list(self._choices)

    def set_current_text(self, text, emit=False):
        self.commit_text(str(text or ""), emit=emit)

    def update_legacy_choice_cache(self, values):
        """兼容 V3 的 `_search_model.setStringList()`，只同步完整候选缓存。"""
        self._choices = list(dict.fromkeys(str(x) for x in (values or []) if str(x)))
        self.combo._search_choices = list(self._choices)


class _LegacySearchModelAdapter(QObject):
    """旧 V2/V3 只调用 setStringList；不再创建 QStringListModel/QCompleter。"""

    def __init__(self, behavior: _SearchComboBehavior):
        super().__init__(behavior.combo)
        self.behavior = behavior

    def setStringList(self, values):
        self.behavior.update_legacy_choice_cache(values)


class SearchComboBox(QComboBox):
    """可输入搜索型下拉框；视觉和普通 QComboBox 完全同源。"""

    valueChanged = pyqtSignal(str)
    textEdited = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_behavior = _SearchComboBehavior(self)
        self._search_model = _LegacySearchModelAdapter(self._search_behavior)
        self._search_behavior.valueCommitted.connect(self.valueChanged)
        self._search_behavior.textEdited.connect(self.textEdited)

    def showPopup(self):
        # 用户主动打开 QComboBox 时显示完整候选；过滤 popup 由 behavior 调基类实现。
        self._search_behavior.show_all()

    def set_choices(self, choices, preserve=True, current=None):
        self._search_behavior.set_choices(choices, preserve=preserve, current=current)

    def setChoices(self, choices, preserve=True, current=None):
        self.set_choices(choices, preserve=preserve, current=current)

    def choices(self):
        return self._search_behavior.choices()

    def setCurrentText(self, text, emit=False):
        self._search_behavior.set_current_text(text, emit=emit)

    def setPlaceholderText(self, text):
        edit = self.lineEdit()
        if edit is not None:
            edit.setPlaceholderText(str(text or ""))

    def hide_popup(self):
        self.hidePopup()


def configure_search_combo(combo: QComboBox):
    """把既有 editable QComboBox 接入同一套单-popup行为。"""
    if combo is None:
        return combo
    if isinstance(combo, SearchComboBox):
        return combo
    behavior = getattr(combo, "_search_behavior", None)
    if behavior is None:
        behavior = _SearchComboBehavior(combo)
        combo._search_behavior = behavior
        combo._search_model = _LegacySearchModelAdapter(behavior)
        combo._search_choices = behavior.choices()
    return combo


def set_search_choices(combo: QComboBox, choices, current=None, preserve=True):
    """兼容旧调用名；新实现不再创建 QCompleter。"""
    if combo is None:
        return
    configure_search_combo(combo)
    behavior = getattr(combo, "_search_behavior", None)
    if behavior is not None:
        behavior.set_choices(choices, preserve=preserve, current=current)
        combo._search_choices = behavior.choices()
