"""模板编辑页侧栏的窄边缘悬停收起/展开控件。"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QSplitter


class _HoverEdgeButton(QToolButton):
    """平时只占一条很窄的边缘，鼠标移入时才显示“竖线 + 箭头”。"""

    clicked_edge = pyqtSignal()

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self._side = side
        self._collapsed = False
        self.setFixedWidth(18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("收起侧栏")
        self.setStyleSheet(
            "QToolButton { border:0; padding:0; margin:0; background:transparent; "
            "font-size:15px; color:#5F6368; }"
            "QToolButton:hover { background:#EEF2F7; }"
        )
        self.clicked.connect(self.clicked_edge.emit)
        self._refresh_text(False)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.setToolTip("展开侧栏" if collapsed else "收起侧栏")
        self._refresh_text(self.underMouse())

    def _glyph(self) -> str:
        if self._side == "left":
            # 左栏在表格左侧：展开时箭头向左收起；收起后向右展开。
            return "│›" if self._collapsed else "‹│"
        # 右栏在表格右侧：展开时箭头向右收起；收起后向左展开。
        return "‹│" if self._collapsed else "│›"

    def _refresh_text(self, hovered: bool):
        self.setText(self._glyph() if hovered else "")

    def enterEvent(self, event):
        self._refresh_text(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._refresh_text(False)
        super().leaveEvent(event)


class CollapsibleSideContainer(QWidget):
    """把任意侧栏包装为可沿表格边缘收起的容器。"""

    toggled = pyqtSignal(bool)  # True = collapsed

    def __init__(self, panel: QWidget, side: str, expanded_width: int, parent=None):
        super().__init__(parent)
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        self._panel = panel
        self._side = side
        self._expanded_width = expanded_width
        self._collapsed = False
        self._edge_width = 18

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._edge = _HoverEdgeButton(side, self)
        self._edge.clicked_edge.connect(self.toggle)

        if side == "left":
            layout.addWidget(panel, 1)
            layout.addWidget(self._edge)
        else:
            layout.addWidget(self._edge)
            layout.addWidget(panel, 1)

        self.setMinimumWidth(self._edge_width + panel.minimumWidth())
        self.setMaximumWidth(self._edge_width + panel.maximumWidth())

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return

        splitter = self.parentWidget()
        splitter_sizes = splitter.sizes() if isinstance(splitter, QSplitter) else None
        splitter_index = splitter.indexOf(self) if isinstance(splitter, QSplitter) else -1

        self._collapsed = collapsed
        self._panel.setVisible(not collapsed)
        self._edge.set_collapsed(collapsed)

        if collapsed:
            self.setMinimumWidth(self._edge_width)
            self.setMaximumWidth(self._edge_width)
            if splitter_sizes is not None and splitter_index >= 0:
                released = max(0, splitter_sizes[splitter_index] - self._edge_width)
                splitter_sizes[splitter_index] = self._edge_width
                # 把释放的宽度优先给中间表格。
                middle = 1 if len(splitter_sizes) > 1 else 0
                splitter_sizes[middle] += released
                splitter.setSizes(splitter_sizes)
        else:
            self.setMinimumWidth(self._edge_width + self._panel.minimumWidth())
            self.setMaximumWidth(self._edge_width + self._panel.maximumWidth())
            if splitter_sizes is not None and splitter_index >= 0:
                target = max(self._expanded_width, self.minimumWidth())
                current = splitter_sizes[splitter_index]
                need = max(0, target - current)
                middle = 1 if len(splitter_sizes) > 1 else 0
                take = min(need, max(0, splitter_sizes[middle] - 240))
                splitter_sizes[splitter_index] = current + take
                splitter_sizes[middle] -= take
                splitter.setSizes(splitter_sizes)

        self.updateGeometry()
        self.toggled.emit(collapsed)
