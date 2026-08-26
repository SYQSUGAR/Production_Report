"""统一可输入下拉框的搜索、光标编辑、真实选择提交与弹层关闭行为。"""

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, QStringListModel, QModelIndex
from PyQt6.QtWidgets import QComboBox, QCompleter


class _LineEditPopupFilter(QObject):
    """鼠标先完成光标定位/选区，再在释放后显示搜索候选。"""

    def __init__(self, combo: QComboBox):
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonRelease:
            QTimer.singleShot(0, self._show_after_editing)
        return False

    def _show_after_editing(self):
        combo = self.combo
        if not combo.isEnabled() or not combo.isVisible() or not combo.isEditable():
            return
        if getattr(combo, "_search_combo_suppress_popup", False):
            return
        edit = combo.lineEdit()
        if edit is None:
            return
        # 拖选/双击形成选区时优先保留文本编辑，不主动弹候选。
        if edit.hasSelectedText():
            return
        _show_filtered_popup(combo)


def _completion_text(value):
    if isinstance(value, QModelIndex):
        return str(value.data() or "")
    return str(value or "")


def _hide_all_popups(combo: QComboBox):
    try:
        combo.hidePopup()
    except RuntimeError:
        return
    comp = combo.completer()
    if comp is not None:
        popup = comp.popup()
        if popup is not None:
            popup.hide()


def _show_filtered_popup(combo: QComboBox):
    if getattr(combo, "_search_combo_suppress_popup", False):
        return
    edit = combo.lineEdit()
    comp = combo.completer()
    if edit is None or comp is None:
        return

    cursor = edit.cursorPosition()
    sel_start = edit.selectionStart()
    sel_len = len(edit.selectedText())
    comp.setCompletionPrefix(edit.text())
    comp.complete()

    # complete() 只负责显示候选，不能改变用户刚完成的光标/选区。
    edit.setFocus(Qt.FocusReason.MouseFocusReason)
    edit.setCursorPosition(min(cursor, len(edit.text())))
    if sel_start >= 0 and sel_len > 0:
        edit.setSelection(sel_start, sel_len)


def _finish_commit(combo: QComboBox, text: str, idx: int):
    """popup 已关闭后再通知业务层，避免 JOIN 联动刷新把候选重新打开。"""
    try:
        _hide_all_popups(combo)
        # 业务层既有 currentTextChanged，也有 activated 监听；统一在 popup 收起后通知。
        combo.currentTextChanged.emit(text)
        if idx >= 0:
            combo.activated.emit(idx)
    except RuntimeError:
        return

    # JOIN/字段刷新链可能包含 0ms/80ms 延迟，再补两次关闭，确保不会残留旧候选层。
    QTimer.singleShot(20, lambda c=combo: _hide_all_popups(c))
    QTimer.singleShot(100, lambda c=combo: _hide_all_popups(c))
    QTimer.singleShot(180, lambda c=combo: setattr(c, "_search_combo_suppress_popup", False))


def _commit_candidate(combo: QComboBox, value):
    """候选选择：先真实提交并关闭 popup，再触发所有业务联动。"""
    text = _completion_text(value).strip()
    combo._search_combo_suppress_popup = True

    if not text:
        _hide_all_popups(combo)
        QTimer.singleShot(100, lambda c=combo: setattr(c, "_search_combo_suppress_popup", False))
        return

    # 关键：提交 currentIndex/currentText 时先阻断 combo 的业务信号。
    # 旧 JOIN 逻辑如果在 setCurrentIndex 期间同步刷新，会把 completer/popup 状态重新刷出来。
    old_block = combo.blockSignals(True)
    try:
        idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # 允许自由文本，不强行改成第一项。
            combo.setCurrentIndex(-1)
        combo.setEditText(text)
        _hide_all_popups(combo)
    finally:
        combo.blockSignals(old_block)

    # 下一轮事件循环再通知业务层，此时候选层已经完成关闭。
    QTimer.singleShot(0, lambda c=combo, t=text, i=idx: _finish_commit(c, t, i))


def configure_search_combo(combo: QComboBox):
    """把一个 editable QComboBox 统一成标准搜索下拉输入框。"""
    if combo is None:
        return combo

    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    edit = combo.lineEdit()

    # 移除历史 V2 的 FocusIn/MousePress 立即弹层过滤器，避免第一次点击抢光标。
    old_filter = getattr(combo, "_contains_popup_filter", None)
    if edit is not None and old_filter is not None:
        try:
            edit.removeEventFilter(old_filter)
        except RuntimeError:
            pass

    values = [combo.itemText(i) for i in range(combo.count())]
    model = getattr(combo, "_unified_search_model", None)
    if model is None:
        model = QStringListModel(values, combo)
        combo._unified_search_model = model
    else:
        model.setStringList(values)

    completer = getattr(combo, "_unified_completer", None)
    if completer is None:
        completer = QCompleter(model, combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated.connect(lambda value, c=combo: _commit_candidate(c, value))
        combo._unified_completer = completer
    else:
        completer.setModel(model)

    if combo.completer() is not completer:
        combo.setCompleter(completer)
    combo._search_model = model  # 兼容旧代码更新候选模型。

    # 旧 V6 可以继续 hide，但不再允许它摘掉 completer。
    combo._v6_detached_completer = True

    popup_filter = getattr(combo, "_unified_popup_filter", None)
    if popup_filter is None:
        popup_filter = _LineEditPopupFilter(combo)
        combo._unified_popup_filter = popup_filter
        if edit is not None:
            edit.installEventFilter(popup_filter)

    if not getattr(combo, "_unified_text_wired", False) and edit is not None:
        def on_text_edited(_text, c=combo):
            if getattr(c, "_search_combo_suppress_popup", False):
                return
            QTimer.singleShot(0, lambda: _show_filtered_popup(c))

        edit.textEdited.connect(on_text_edited)
        combo._unified_text_wired = True

    if not getattr(combo, "_unified_combo_wired", False):
        # 右侧箭头原生列表由 QComboBox 自己提交 currentIndex；选择后立即关闭搜索候选层。
        combo.activated.connect(lambda *_args, c=combo: _hide_all_popups(c))
        combo._unified_combo_wired = True

    combo._unified_search_configured = True
    return combo


def set_search_choices(combo: QComboBox, choices, current=None):
    """更新完整候选，保留自由文本，并保持箭头列表与搜索模型一致。"""
    if combo is None:
        return
    values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
    text = combo.currentText() if current is None else str(current)

    old = combo.blockSignals(True)
    combo.clear()
    combo.addItems(values)
    idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentIndex(-1)
        combo.setEditText(text)
    combo.blockSignals(old)

    configure_search_combo(combo)
    model = getattr(combo, "_unified_search_model", None)
    if model is not None:
        model.setStringList(values)
    combo._search_choices = values
