"""统一可输入下拉框的搜索、光标编辑、真实选择提交与弹层关闭行为。"""

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, QStringListModel, QModelIndex
from PyQt6.QtWidgets import QComboBox, QCompleter


class _LineEditPopupFilter(QObject):
    """鼠标先完成光标定位/选区，再在释放后显示搜索候选。"""

    def __init__(self, combo: QComboBox):
        super().__init__(combo)
        self.combo = combo
        self._pressed_selection = None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            edit = self.combo.lineEdit()
            if edit is not None:
                self._pressed_selection = (edit.selectionStart(), len(edit.selectedText()))
            return False

        if event.type() == QEvent.Type.MouseButtonRelease:
            QTimer.singleShot(0, self._show_after_editing)
            return False

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
        # 用户拖选/双击形成选区时优先保留文本编辑，不主动弹候选。
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
    edit.setCursorPosition(min(cursor, len(edit.text())))
    if sel_start >= 0 and sel_len > 0:
        edit.setSelection(sel_start, sel_len)


def _commit_candidate(combo: QComboBox, value):
    text = _completion_text(value).strip()
    if not text:
        _hide_all_popups(combo)
        return

    combo._search_combo_suppress_popup = True
    try:
        idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            # 真实选择必须落在 QComboBox 的 currentIndex 上，避免显示值与实际值不一致。
            combo.setCurrentIndex(idx)
        combo.setEditText(text)
        _hide_all_popups(combo)
    finally:
        QTimer.singleShot(80, lambda c=combo: setattr(c, "_search_combo_suppress_popup", False))


def configure_search_combo(combo: QComboBox):
    """把一个 editable QComboBox 统一成标准搜索下拉输入框。"""
    if combo is None:
        return combo

    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

    # 移除历史 V2 的 FocusIn/MousePress 立即弹层过滤器，避免第一次点击抢走光标编辑体验。
    old_filter = getattr(combo, "_contains_popup_filter", None)
    edit = combo.lineEdit()
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

    completer = QCompleter(model, combo)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    combo.setCompleter(completer)
    combo._search_model = model  # 兼容旧代码更新候选模型。

    # 阻止旧 V6 选择后“摘掉 completer”的逻辑再次介入；旧逻辑仍可负责 hide，但不再改控件结构。
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

    # completer 每次重建都重新绑定，真正的候选选择由这里提交到 QComboBox。
    completer.activated.connect(lambda value, c=combo: _commit_candidate(c, value))

    if not getattr(combo, "_unified_combo_wired", False):
        # 右侧箭头的原生列表由 QComboBox 自己设置 currentIndex，这里只统一收尾关闭。
        combo.activated.connect(lambda *_args, c=combo: _hide_all_popups(c))
        combo._unified_combo_wired = True

    return combo


def set_search_choices(combo: QComboBox, choices, current=None):
    """更新完整候选，保留当前自由文本，并保持 native 列表与 completer 模型一致。"""
    if combo is None:
        return
    values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
    text = combo.currentText() if current is None else str(current)

    old = combo.blockSignals(True)
    combo.clear()
    combo.addItems(values)
    combo.setEditText(text)
    combo.blockSignals(old)

    configure_search_combo(combo)
    model = getattr(combo, "_unified_search_model", None)
    if model is not None:
        model.setStringList(values)
    combo._search_choices = values
