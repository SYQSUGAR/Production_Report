"""统一的可输入搜索下拉框。

整个程序的下拉控件只保留两类：
- QComboBox：不可输入，只从固定候选中选择；
- SearchComboBox(QComboBox)：可输入、可搜索、允许自由文本。

SearchComboBox 只使用 QComboBox 自己的 popup，不使用 QCompleter 第二层弹窗。
"""

from __future__ import annotations

from PyQt6 import sip
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
        self._destroyed = False
        self._pending_filter_text: str | None = None

        combo.destroyed.connect(self._mark_destroyed)
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

    # ------------------------------------------------------------------
    # 生命周期保护。Qt 的 deleteLater()/父控件销毁过程中，事件队列里仍可能留有
    # MouseRelease、ToolTip、singleShot 等事件；此时 Python wrapper 还存在，但
    # 底层 C++ QComboBox 已经删除。所有入口必须先检查对象有效性。
    # ------------------------------------------------------------------
    def _mark_destroyed(self, *_args):
        self._destroyed = True
        self._pending_filter_text = None
        self.combo = None

    def _combo(self):
        if self._destroyed:
            return None
        combo = self.combo
        if combo is None:
            return None
        try:
            if sip.isdeleted(combo):
                self._destroyed = True
                self.combo = None
                return None
        except Exception:
            self._destroyed = True
            self.combo = None
            return None
        return combo

    def _edit(self):
        combo = self._combo()
        if combo is None:
            return None
        try:
            edit = combo.lineEdit()
            if edit is None or sip.isdeleted(edit):
                return None
            return edit
        except (RuntimeError, AttributeError):
            return None

    def _popup_visible(self):
        combo = self._combo()
        if combo is None:
            return False
        try:
            view = combo.view()
            return view is not None and not sip.isdeleted(view) and view.isVisible()
        except (RuntimeError, AttributeError):
            return False

    def eventFilter(self, watched, event):
        combo = self._combo()
        if combo is None:
            return False
        edit = self._edit()

        if edit is not None and watched is edit:
            if event.type() == QEvent.Type.MouseButtonRelease:
                # QLineEdit 先处理本次点击，下一轮事件循环才展开候选。
                QTimer.singleShot(0, self._show_after_mouse_release)
            elif event.type() == QEvent.Type.ToolTip:
                try:
                    text = edit.text()
                    if text and edit.fontMetrics().horizontalAdvance(text) > edit.contentsRect().width() - 8:
                        edit.setToolTip(text)
                    else:
                        edit.setToolTip("")
                except RuntimeError:
                    return False
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
            except (RuntimeError, AttributeError):
                pass
            return False

        return False

    def _show_after_mouse_release(self):
        combo = self._combo()
        edit = self._edit()
        if combo is None or edit is None or self._committing or self._updating:
            return
        try:
            if not combo.isEnabled() or not combo.isVisible():
                return
            # 拖选、双击选字形成选区时，优先保留文字编辑，不主动弹候选。
            if edit.hasSelectedText():
                return
        except RuntimeError:
            return
        self.show_filtered()

    def _filtered_choices(self, text: str):
        key = str(text or "").strip().casefold()
        if not key:
            return list(self._choices)
        return [value for value in self._choices if key in value.casefold()]

    def _on_text_edited(self, text: str):
        if self._combo() is None or self._updating or self._committing:
            return
        self.textEdited.emit(text)
        self._pending_filter_text = str(text)
        QTimer.singleShot(0, self._apply_pending_filter)

    def _apply_pending_filter(self):
        if self._combo() is None:
            self._pending_filter_text = None
            return
        if self._pending_filter_text is None or self._committing:
            return
        edit = self._edit()
        if edit is None:
            self._pending_filter_text = None
            return
        try:
            text = edit.text()
        except RuntimeError:
            self._pending_filter_text = None
            return
        self._pending_filter_text = None
        self.show_filtered(text)

    def show_filtered(self, text: str | None = None):
        combo = self._combo()
        edit = self._edit()
        if combo is None or edit is None or self._committing or self._updating:
            return
        try:
            if not combo.isEnabled() or not combo.isVisible():
                return
            current = edit.text() if text is None else str(text)
        except RuntimeError:
            return
        values = self._filtered_choices(current)
        self._apply_visible_choices(values, current, restore_edit_state=True)
        combo = self._combo()
        if combo is None:
            return
        try:
            if not values:
                combo.hidePopup()
                return
            # 只打开 QComboBox 自己的 popup，没有第二层 QCompleter。
            QComboBox.showPopup(combo)
            QTimer.singleShot(0, self._restore_edit_focus)
        except RuntimeError:
            return

    def show_all(self):
        combo = self._combo()
        if combo is None:
            return
        try:
            current = combo.currentText()
        except RuntimeError:
            return
        self._apply_visible_choices(self._choices, current, restore_edit_state=True)
        combo = self._combo()
        if combo is None:
            return
        try:
            QComboBox.showPopup(combo)
        except RuntimeError:
            return

    def _restore_edit_focus(self):
        combo = self._combo()
        edit = self._edit()
        if combo is None or edit is None:
            return
        try:
            if combo.isVisible():
                edit.setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            return

    def _apply_visible_choices(self, values, current_text: str, restore_edit_state=True):
        combo = self._combo()
        edit = self._edit()
        if combo is None or edit is None:
            return

        try:
            cursor = edit.cursorPosition()
            sel_start = edit.selectionStart()
            selected_len = len(edit.selectedText())
        except RuntimeError:
            return
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
        except RuntimeError:
            return
        finally:
            self._updating = False

    def _on_activated(self, index: int):
        if self._combo() is None or self._updating:
            return
        combo = self._combo()
        if combo is None:
            return
        try:
            text = combo.itemText(index).strip() if 0 <= index < combo.count() else combo.currentText().strip()
        except RuntimeError:
            return
        self.commit_text(text, emit=True)

    def _on_editing_finished(self):
        combo = self._combo()
        if combo is None or self._updating or self._committing:
            return
        if self._popup_visible():
            return
        try:
            text = combo.currentText().strip()
        except RuntimeError:
            return
        if text != self._committed_text:
            self.commit_text(text, emit=True)

    def commit_text(self, text: str, emit=True):
        combo = self._combo()
        edit = self._edit()
        if combo is None or edit is None:
            return
        text = str(text or "").strip()
        self._committing = True
        try:
            # 提交后恢复完整候选；自由文本没有匹配项时保持 index=-1。
            self._apply_visible_choices(self._choices, text, restore_edit_state=False)
            combo = self._combo()
            edit = self._edit()
            if combo is None or edit is None:
                return
            idx = combo.findText(text, Qt.MatchFlag.MatchExactly)
            with QSignalBlocker(combo), QSignalBlocker(edit):
                combo.setCurrentIndex(idx if idx >= 0 else -1)
                combo.setEditText(text)
                edit.setCursorPosition(len(text))
            combo.hidePopup()
            self._committed_text = text
        except RuntimeError:
            return
        finally:
            self._committing = False
        if emit and self._combo() is not None:
            self.valueCommitted.emit(text)

    def set_choices(self, choices, preserve=True, current=None):
        combo = self._combo()
        if combo is None:
            return
        values = list(dict.fromkeys(str(x) for x in (choices or []) if str(x)))
        try:
            text = combo.currentText() if current is None else str(current)
        except RuntimeError:
            return
        if not preserve and current is None:
            text = ""
        self._choices = values
        try:
            combo._search_choices = list(values)
        except RuntimeError:
            return
        self._apply_visible_choices(values, text, restore_edit_state=False)
        self._committed_text = text.strip()

    def choices(self):
        return list(self._choices)

    def set_current_text(self, text, emit=False):
        if self._combo() is None:
            return
        self.commit_text(str(text or ""), emit=emit)

    def update_legacy_choice_cache(self, values):
        """兼容 V3 的 `_search_model.setStringList()`，只同步完整候选缓存。"""
        self._choices = list(dict.fromkeys(str(x) for x in (values or []) if str(x)))
        combo = self._combo()
        if combo is not None:
            try:
                combo._search_choices = list(self._choices)
            except RuntimeError:
                pass


class _LegacySearchModelAdapter(QObject):
    """旧 V2/V3 只调用 setStringList；不再创建 QStringListModel/QCompleter。"""

    def __init__(self, behavior: _SearchComboBehavior):
        parent = behavior._combo()
        super().__init__(parent)
        self.behavior = behavior

    def setStringList(self, values):
        behavior = self.behavior
        if behavior is None or behavior._combo() is None:
            return
        behavior.update_legacy_choice_cache(values)


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
        behavior = getattr(self, "_search_behavior", None)
        if behavior is None or behavior._combo() is None:
            return
        # 用户主动打开 QComboBox 时显示完整候选；过滤 popup 由 behavior 调基类实现。
        behavior.show_all()

    def set_choices(self, choices, preserve=True, current=None):
        behavior = getattr(self, "_search_behavior", None)
        if behavior is not None:
            behavior.set_choices(choices, preserve=preserve, current=current)

    def setChoices(self, choices, preserve=True, current=None):
        self.set_choices(choices, preserve=preserve, current=current)

    def choices(self):
        behavior = getattr(self, "_search_behavior", None)
        return behavior.choices() if behavior is not None else []

    def setCurrentText(self, text, emit=False):
        behavior = getattr(self, "_search_behavior", None)
        if behavior is not None:
            behavior.set_current_text(text, emit=emit)

    def setPlaceholderText(self, text):
        try:
            if sip.isdeleted(self):
                return
            edit = self.lineEdit()
            if edit is not None and not sip.isdeleted(edit):
                edit.setPlaceholderText(str(text or ""))
        except RuntimeError:
            return

    def hide_popup(self):
        try:
            if not sip.isdeleted(self):
                self.hidePopup()
        except RuntimeError:
            return


def configure_search_combo(combo: QComboBox):
    """把既有 editable QComboBox 接入同一套单-popup行为。"""
    if combo is None:
        return combo
    try:
        if sip.isdeleted(combo):
            return combo
    except Exception:
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
    try:
        if sip.isdeleted(combo):
            return
    except Exception:
        return
    configure_search_combo(combo)
    behavior = getattr(combo, "_search_behavior", None)
    if behavior is not None:
        behavior.set_choices(choices, preserve=preserve, current=current)
        try:
            combo._search_choices = behavior.choices()
        except RuntimeError:
            pass
