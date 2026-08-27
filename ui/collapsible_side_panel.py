"""模板编辑页左右侧栏：外侧隐藏控制 + 内侧拖拽调宽。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QSplitter, QSplitterHandle


class SidebarToggleStrip(QWidget):
    """只负责侧栏隐藏/显示的外侧控制条。

    该控件不属于 QSplitter，也不参与侧栏宽度拖拽：
    - 左侧样式栏：控制条固定在整个编辑区最左侧；
    - 右侧数据库栏：控制条固定在整个编辑区最右侧。
    平时透明，鼠标进入后才显示竖条和箭头。
    """

    HOT_WIDTH = 16

    def __init__(self, splitter, side_name: str, parent=None):
        super().__init__(parent)
        self._splitter = splitter
        self._side_name = side_name
        self._hovered = False
        self.setFixedWidth(self.HOT_WIDTH)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击收起/展开侧栏")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._splitter.toggle_side(self._side_name)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if not self._hovered:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(238, 243, 249, 215))

        x = self.width() // 2
        painter.setPen(QPen(QColor("#98A2B1"), 1))
        painter.drawLine(x, 2, x, max(2, self.height() - 2))

        direction = self._splitter.arrow_direction(self._side_name)
        cy = self.height() // 2
        painter.setPen(QPen(
            QColor("#1677FF"), 2.2,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        ))
        half_w = 4
        half_h = 6
        if direction == "left":
            painter.drawLine(x + half_w, cy - half_h, x - half_w, cy)
            painter.drawLine(x - half_w, cy, x + half_w, cy + half_h)
        else:
            painter.drawLine(x - half_w, cy - half_h, x + half_w, cy)
            painter.drawLine(x + half_w, cy, x - half_w, cy + half_h)


class _SidebarResizeHandle(QSplitterHandle):
    """只负责拖拽调宽，绝不处理隐藏/展开。"""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setToolTip("拖动调整侧栏宽度")


class CollapsibleSplitter(QSplitter):
    """模板编辑三栏布局。

    QSplitter 内部只存在两个可拖动边界：
    1. 样式栏右边界（样式栏 ↔ 表格）；
    2. 数据库栏左边界（表格 ↔ 数据库栏）。

    样式栏最左侧和数据库栏最右侧没有 splitter handle，隐藏/显示由
    外部 SidebarToggleStrip 独立完成，因此不会再出现额外可拖边界。
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(5)
        self.setChildrenCollapsible(True)
        self._side_specs = {}
        self._toggle_strips = {}

    def createHandle(self):
        return _SidebarResizeHandle(self.orientation(), self)

    def configure_side(
        self,
        side_name: str,
        panel_index: int,
        expanded_width: int,
        center_index: int = 1,
    ):
        widget = self.widget(panel_index)
        self._side_specs[side_name] = {
            "panel_index": panel_index,
            "center_index": center_index,
            "expanded_width": expanded_width,
            "last_width": expanded_width,
            "minimum_width": widget.minimumWidth(),
            "maximum_width": widget.maximumWidth(),
        }
        self.setCollapsible(panel_index, True)

    def register_toggle_strip(self, side_name: str, strip: SidebarToggleStrip):
        self._toggle_strips[side_name] = strip

    def side_collapsed(self, side_name: str) -> bool:
        spec = self._side_specs[side_name]
        return self.sizes()[spec["panel_index"]] <= 1

    def arrow_direction(self, side_name: str) -> str:
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
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(16777215)
            sizes[panel_index] = 0
            sizes[center_index] += current
            self.setSizes(sizes)
        else:
            if current > 1:
                return
            widget.setMinimumWidth(spec["minimum_width"])
            widget.setMaximumWidth(spec["maximum_width"])
            target = max(
                spec["last_width"],
                spec["expanded_width"],
                spec["minimum_width"],
            )
            available = max(0, sizes[center_index] - 260)
            restore = min(target, available) if available else target
            sizes[panel_index] = restore
            sizes[center_index] = max(0, sizes[center_index] - restore)
            self.setSizes(sizes)

        strip = self._toggle_strips.get(side_name)
        if strip is not None:
            strip.update()
