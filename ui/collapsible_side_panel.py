"""模板编辑页左右侧栏：拖拽调宽与收起/展开使用独立交互区域。"""

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QSplitter


class _SidebarToggleStrip(QWidget):
    """独立于 QSplitterHandle 的侧栏收起/展开热区。

    它位于拖拽分隔线的“表格一侧”，不覆盖分隔线本身：
    - 分隔线只负责拖动调宽；
    - 本控件只负责点击收起/展开；
    - 平时完全透明，鼠标进入后才显示细长竖条和中间箭头。
    """

    HOT_WIDTH = 14

    def __init__(self, splitter, side_name: str):
        super().__init__(splitter)
        self._splitter = splitter
        self._side_name = side_name
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击收起/展开侧栏")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.raise_()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # 这里只响应点击，不把事件传给 QSplitterHandle，因此不会触发拖拽。
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self._splitter.toggle_side(self._side_name)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if not self._hovered:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 热区可以稍宽以便鼠标命中，但视觉上只画一条很细的长竖条。
        painter.fillRect(self.rect(), QColor(238, 243, 249, 155))
        x = self.width() // 2
        painter.setPen(QPen(QColor("#A4AFBC"), 1))
        painter.drawLine(x, 4, x, max(4, self.height() - 4))

        direction = self._splitter.arrow_direction(self._side_name)
        cy = self.height() // 2
        painter.setPen(QPen(
            QColor("#1A73E8"), 1.8, Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
        ))

        span = 3
        # 画成类似示例中的双折线箭头，位于整条控制带中部。
        for offset in (-4, 4):
            yy = cy + offset
            if direction == "left":
                painter.drawLine(x + span, yy - span, x - span, yy)
                painter.drawLine(x - span, yy, x + span, yy + span)
            else:
                painter.drawLine(x - span, yy - span, x + span, yy)
                painter.drawLine(x + span, yy, x - span, yy + span)


class CollapsibleSplitter(QSplitter):
    """三栏编辑区的 QSplitter。

    QSplitter 自己的 handle 只负责拖动改变宽度；每个侧栏另有一条独立的
    _SidebarToggleStrip 负责点击收起/展开。两套区域相邻但绝不共用事件。
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        # 拖拽分隔线本身保持窄，直接贴在侧栏边缘。
        self.setHandleWidth(5)
        self.setChildrenCollapsible(True)
        self._side_specs = {}
        self._toggle_strips = {}

        # resize/move 时重新定位覆盖在表格侧的 toggle strip。
        self.installEventFilter(self)

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

        strip = _SidebarToggleStrip(self, side_name)
        self._toggle_strips[side_name] = strip
        strip.show()
        self._position_toggle_strips()

    def eventFilter(self, watched, event):
        if watched is self and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Show,
        ):
            self._position_toggle_strips()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toggle_strips()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_toggle_strips()

    def _position_toggle_strips(self):
        """把隐藏/展示热区放在拖拽 handle 的表格一侧。

        左侧： [侧栏][拖拽 handle][toggle strip][表格]
        右侧： [表格][toggle strip][拖拽 handle][侧栏]
        """
        if not self._side_specs:
            return

        height = max(0, self.height())
        width = _SidebarToggleStrip.HOT_WIDTH
        for side_name, spec in self._side_specs.items():
            strip = self._toggle_strips.get(side_name)
            handle = self.handle(spec["handle_index"])
            if strip is None or handle is None:
                continue

            hg = handle.geometry()
            if side_name == "left":
                x = hg.right() + 1
            else:
                x = hg.left() - width

            # 防止极端窗口尺寸下越界。
            x = max(0, min(x, max(0, self.width() - width)))
            strip.setGeometry(x, 0, width, height)
            strip.raise_()

    def side_collapsed(self, side_name: str) -> bool:
        spec = self._side_specs[side_name]
        sizes = self.sizes()
        return sizes[spec["panel_index"]] <= 1

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
            sizes[panel_index] = 0
            sizes[center_index] += current
            self.setSizes(sizes)
        else:
            if current > 1:
                return
            widget.setMinimumWidth(spec["minimum_width"])
            target = max(
                spec["last_width"], spec["expanded_width"], spec["minimum_width"]
            )
            available = max(0, sizes[center_index] - 260)
            restore = min(target, available) if available else target
            sizes[panel_index] = restore
            sizes[center_index] = max(0, sizes[center_index] - restore)
            self.setSizes(sizes)

        self._position_toggle_strips()
        strip = self._toggle_strips.get(side_name)
        if strip is not None:
            strip.update()
