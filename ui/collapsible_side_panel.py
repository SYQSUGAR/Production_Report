"""模板编辑页左右侧栏：可拖拽分隔线 + 悬停整条边缘收起/展开。"""

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSplitter, QSplitterHandle


class _SidebarSplitterHandle(QSplitterHandle):
    """贴着侧栏的分隔线。

    平时保持透明，只承担正常的拖拽调宽；鼠标进入分隔线附近时，整条竖向
    热区才显示出来，并在高度中点绘制一个小箭头。轻点箭头区域收起/展开，
    拖动则仍按普通 QSplitterHandle 调整侧栏宽度。
    """

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self._press_pos = QPoint()
        self._side_name = ""
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SplitHCursor)

    def configure(self, side_name: str):
        self._side_name = side_name
        self.setToolTip("拖动调整侧栏宽度；单击收起/展开")
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        super().mouseReleaseEvent(event)
        if moved <= 3 and self._side_name:
            self.splitter().toggle_side(self._side_name)

    def paintEvent(self, event):
        # 平时不画任何常驻按钮/边条；只有鼠标靠近分隔线时才浮出整条控制带。
        if not self._hovered:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(237, 242, 248, 225))

        x = self.width() // 2
        painter.setPen(QPen(QColor("#9AA4B2"), 1))
        painter.drawLine(x, 0, x, self.height())

        direction = self.splitter().arrow_direction(self._side_name)
        cy = self.height() // 2
        arrow_color = QColor("#1A73E8")
        painter.setPen(QPen(arrow_color, 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        # 在中间画紧凑双折线箭头，效果接近用户示例中的蓝色箭头标记。
        span = max(2, min(4, self.width() // 3))
        for offset in (-3, 3):
            yy = cy + offset
            if direction == "left":
                painter.drawLine(x + span, yy - span, x - span, yy)
                painter.drawLine(x - span, yy, x + span, yy + span)
            else:
                painter.drawLine(x - span, yy - span, x + span, yy)
                painter.drawLine(x + span, yy, x - span, yy + span)


class CollapsibleSplitter(QSplitter):
    """三栏编辑区的 QSplitter。

    左右侧栏收起时大小真正变为 0，不留下常驻侧栏容器；只有贴着边界的
    QSplitterHandle 还存在，用作拖拽和悬停展开入口。
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(10)
        self.setChildrenCollapsible(True)
        self._side_specs = {}

    def createHandle(self):
        return _SidebarSplitterHandle(self.orientation(), self)

    def configure_side(
        self,
        side_name: str,
        panel_index: int,
        handle_index: int,
        expanded_width: int,
        center_index: int = 1,
    ):
        widget = self.widget(panel_index)
        self._side_specs[side_name] = {
            "panel_index": panel_index,
            "handle_index": handle_index,
            "center_index": center_index,
            "expanded_width": expanded_width,
            "last_width": expanded_width,
            "minimum_width": widget.minimumWidth(),
        }
        self.setCollapsible(panel_index, True)
        handle = self.handle(handle_index)
        if isinstance(handle, _SidebarSplitterHandle):
            handle.configure(side_name)

    def side_collapsed(self, side_name: str) -> bool:
        spec = self._side_specs[side_name]
        sizes = self.sizes()
        return sizes[spec["panel_index"]] <= 1

    def arrow_direction(self, side_name: str) -> str:
        """返回当前点击箭头应指向的方向。"""
        collapsed = self.side_collapsed(side_name)
        if side_name == "left":
            return "right" if collapsed else "left"
        return "left" if collapsed else "right"

    def toggle_side(self, side_name: str):
        self.set_side_collapsed(side_name, not self.side_collapsed(side_name))

    def set_side_collapsed(self, side_name: str, collapsed: bool):
        spec = self._side_specs[side_name]
        panel_index = spec["panel_index"]
        center_index = spec["center_index"]
        widget = self.widget(panel_index)
        sizes = self.sizes()
        current = sizes[panel_index]

        if collapsed:
            if current <= 1:
                return
            spec["last_width"] = current
            # 临时允许大小降到 0；不 hide widget，否则对应 splitter handle 也会消失。
            widget.setMinimumWidth(0)
            sizes[panel_index] = 0
            sizes[center_index] += current
            self.setSizes(sizes)
        else:
            if current > 1:
                return
            widget.setMinimumWidth(spec["minimum_width"])
            target = max(spec["last_width"], spec["expanded_width"], spec["minimum_width"])
            available = max(0, sizes[center_index] - 260)
            restore = min(target, available) if available else target
            sizes[panel_index] = restore
            sizes[center_index] = max(0, sizes[center_index] - restore)
            self.setSizes(sizes)

        for data in self._side_specs.values():
            handle = self.handle(data["handle_index"])
            if handle is not None:
                handle.update()
