"""模板编辑页左右侧栏：拖拽调宽与收起/展开使用独立交互区域。"""

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QSplitter, QSplitterHandle


class _SidebarToggleStrip(QWidget):
    """独立于 QSplitterHandle 的侧栏收起/展开热区。

    本控件只负责点击收起/展开，不参与拖拽。平时透明，鼠标进入后显示
    一条贴边的细长控制带，并在高度中部绘制清晰箭头。
    """

    HOT_WIDTH = 16

    def __init__(self, splitter, side_name: str):
        super().__init__(splitter)
        self._splitter = splitter
        self._side_name = side_name
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击收起/展开侧栏")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.raise_()

    def enterEvent(self, event):
        self._hovered = True
        self.raise_()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self._splitter.toggle_side(self._side_name)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if not self._hovered:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 热区宽度适合点击，但视觉条保持很窄，不挡表格。
        painter.fillRect(self.rect(), QColor(238, 243, 249, 215))
        x = self.width() // 2
        painter.setPen(QPen(QColor("#98A2B1"), 1))
        painter.drawLine(x, 2, x, max(2, self.height() - 2))

        direction = self._splitter.arrow_direction(self._side_name)
        cy = self.height() // 2

        # 不使用字体字符，直接画折线箭头，避免不同系统字体下箭头消失。
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
    """只负责尺寸拖拽的分隔线，绝不处理隐藏/展开点击。"""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._resize_enabled = True
        self.setMouseTracking(True)

    def set_resize_enabled(self, enabled: bool):
        self._resize_enabled = bool(enabled)
        self.setCursor(
            Qt.CursorShape.SplitHCursor if self._resize_enabled
            else Qt.CursorShape.ArrowCursor
        )
        self.setToolTip("拖动调整侧栏宽度" if self._resize_enabled else "")

    def mousePressEvent(self, event):
        if not self._resize_enabled:
            event.ignore()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._resize_enabled:
            event.ignore()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._resize_enabled:
            event.ignore()
            return
        super().mouseReleaseEvent(event)


class CollapsibleSplitter(QSplitter):
    """三栏编辑区的 QSplitter。

    左侧字体栏和右侧数据库栏都只允许从“靠表格的一侧”调整宽度：
    - 字体栏：右边界可拖动；
    - 数据库栏：左边界可拖动；
    数据库栏最右侧是窗口外边缘，不存在任何额外拖动边界。

    两侧的隐藏/展开都由独立悬停控制带完成，与拖拽分隔线完全分开。
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(5)
        self.setChildrenCollapsible(True)
        self._side_specs = {}
        self._toggle_strips = {}
        self.installEventFilter(self)
        self.splitterMoved.connect(lambda *_: self._position_toggle_strips())

    def createHandle(self):
        return _SidebarResizeHandle(self.orientation(), self)

    def configure_side(
        self,
        side_name: str,
        panel_index: int,
        handle_index: int,
        expanded_width: int,
        center_index: int = 1,
        resizable: bool = True,
    ):
        widget = self.widget(panel_index)
        self._side_specs[side_name] = {
            "panel_index": panel_index,
            "handle_index": handle_index,
            "center_index": center_index,
            "expanded_width": expanded_width,
            "last_width": expanded_width,
            "minimum_width": widget.minimumWidth(),
            "maximum_width": widget.maximumWidth(),
            "resizable": bool(resizable),
        }
        self.setCollapsible(panel_index, True)

        handle = self.handle(handle_index)
        if isinstance(handle, _SidebarResizeHandle):
            handle.set_resize_enabled(resizable)

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
        """把隐藏控制带放在拖拽线的表格一侧，两种操作区域不重叠。"""
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
                # 字体栏 | 拖拽线 | 隐藏热区 | 表格
                x = hg.right() + 1
            else:
                # 表格 | 隐藏热区 | 拖拽线 | 数据库栏
                x = hg.left() - width

            x = max(0, min(x, max(0, self.width() - width)))
            strip.setGeometry(x, 0, width, height)
            strip.show()
            strip.raise_()
            strip.update()

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
            strip.raise_()
            strip.update()
