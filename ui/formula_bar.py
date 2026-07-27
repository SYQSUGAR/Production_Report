"""公式编辑栏 —— 用于录入静态文字或数据库查询语句，支持多行编辑与批量赋值。"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QTextEdit, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal


class FormulaBar(QWidget):
    """表格上方的公式编辑栏。

    信号:
        content_changed(row, col, text)  —— 单元格内容变更
        batch_apply(text)               —— 批量赋值为选中区域
    """

    content_changed = pyqtSignal(int, int, str)
    batch_apply = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_row = -1
        self._current_col = -1
        self._suppress_update = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # 单元格位置标签
        self._lbl_pos = QLabel("")
        self._lbl_pos.setFixedWidth(80)
        self._lbl_pos.setStyleSheet("font-weight:bold; color:#5F6368; background:#F1F3F7; border-radius:4px; padding:2px 6px;")
        layout.addWidget(self._lbl_pos)

        # 公式标签 (fx)
        lbl_fx = QLabel("fx")
        lbl_fx.setFixedWidth(24)
        lbl_fx.setStyleSheet("font-style:italic; color:#A0A8B4; font-weight:bold;")
        layout.addWidget(lbl_fx)

        # 编辑区域（多行文本）
        self._editor = QTextEdit()
        self._editor.setFixedHeight(52)
        self._editor.setPlaceholderText("输入静态文字或 SQL 查询语句…")
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor, 1)

        # 批量赋值按钮
        self._btn_batch = QPushButton("批量赋值")
        self._btn_batch.setFixedWidth(80)
        self._btn_batch.setToolTip("将当前内容批量赋值到选中的多个单元格")
        self._btn_batch.clicked.connect(self._on_batch_clicked)
        layout.addWidget(self._btn_batch)

    def set_current_cell(self, row: int, col: int, text: str = ""):
        """更新当前选中单元格并显示其内容。"""
        self._current_row = row
        self._current_col = col
        self._lbl_pos.setText(f"{chr(65 + col)}{row + 1}" if row >= 0 and col >= 0 else "")
        self._suppress_update = True
        self._editor.setPlainText(text)
        self._suppress_update = False

    def get_content(self) -> str:
        return self._editor.toPlainText()

    def set_content(self, text: str):
        self._suppress_update = True
        self._editor.setPlainText(text)
        self._suppress_update = False

    def _on_text_changed(self):
        if self._suppress_update:
            return
        if self._current_row >= 0 and self._current_col >= 0:
            text = self._editor.toPlainText()
            # 保存光标位置
            cursor = self._editor.textCursor()
            pos = cursor.position()
            self.content_changed.emit(self._current_row, self._current_col, text)
            # 信号链中可能触发了 setPlainText 导致光标复位，恢复之
            restored = self._editor.textCursor()
            if restored.position() != pos:
                restored.setPosition(min(pos, len(self._editor.toPlainText())))
                self._editor.setTextCursor(restored)

    def _on_batch_clicked(self):
        text = self._editor.toPlainText()
        self.batch_apply.emit(text)
