"""模板编辑页左右侧栏：拖拽调宽与收起/展开使用独立交互区域。"""

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import QWidget, QSplitter, QSplitterHandle


class _SidebarToggleStrip(QWidget):
    """独立于 QSplitterHandle 的侧栏收起/展开热区。

    左侧栏的拖拽线与本控件完全分离；右侧数据库栏不允许拖动，只保留
    本控件用于隐藏/展开。控件平时透明，鼠标进入后显示细竖条和中部箭头。
    """

    HOT_WIDTH = 18

    def __init__(self, splitter, side_name: str):
        super().__init__(splitter)
        self._splitter = splitter
        self._side_name = side_name
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击收起/展开侧栏")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
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

        # 视觉只是一条很窄的悬停控制带，实际命中宽度稍大，方便操作。
        painter.fillRect(self.rect(), QColor(238, 243, 249, 190))
        x = self.width() // 2
        painter.setPen(QPen(QColor("#9AA4B2"), 1))
        painter.drawLine(x, 3, x, max(3, self.height() - 3))

        direction = self._splitter.arrow_direction(self._side_name)
        cy = self.height() // 2

        # 用清晰的大号单箭头替代之前过小的折线，保证实际界面中能看到。
        painter.setPen(QColor("#1A73E8"))
        font = QFont()
        font.setPixelSize(19)
        font.setBold(True)
        painter.setFont(font)
        glyph = "‹" if direction == "left" else "›"
        arrow_rect = self.rect().adjusted(0, cy - 15, 0, -(self.height() - cy - 15))
        painter.drawText(arrow_rect, Qt.AlignmentFlag.AlignCenter, glyph)


class _SidebarResizeHandle(QSplitterHandle):
    """只负责尺寸拖拽的分隔线。

    右侧数据库栏的分隔线会被配置为 fixed，从而不再显示拖拽光标，
    也不接受拖动；左侧字体栏仍保留正常的宽度调整能力。
    """

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

    左侧字体栏：可拖动调宽 + 独立隐藏/展开热区。
    右侧数据库栏：固定宽度 + 独立隐藏/展开热区，不允许拖动边界。
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(5)
        self.setChildrenCollapsible(True)
        self._side_specs = {}
        self._toggle_strips = {}
        self.installEventFilter(self)

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
        self._enforce_fixed_sides()
        self._position_toggle_strips()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_toggle_strips()

    def _enforce_fixed_sides(self):
        """保证展开状态下不可缩放侧栏维持设定宽度。"""
        if not self._side_specs:
            return
        sizes = self.sizes()
        changed = False
        for spec in self._side_specs.values():
            if spec["resizable"]:
                continue
            panel_index = spec["panel_index"]
            center_index = spec["center_index"]
            if sizes[panel_index] <= 1:
                continue
            target = spec["expanded_width"]
            delta = target - sizes[panel_index]
            if delta == 0:
                continue
            sizes[panel_index] = target
            sizes[center_index] = max(0, sizes[center_index] - delta)
            changed = True
        if changed:
            self.setSizes(sizes)

    def _position_toggle_strips(self):
        """隐藏/展示热区与拖拽区域分开，并始终抬到最前层。"""
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
                # 左侧：侧栏 | 拖拽线 | 隐藏热区 | 表格
                x = hg.right() + 1
            else:
                # 右侧：表格 | 隐藏热区 | 固定边界 | 数据库栏
                x = hg.left() - width

            x = max(0, min(x, max(0, self.width() - width)))
            strip.setGeometry(x, 0, width, height)
            strip.show()
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
            widget.setMaximumWidth(16777215)
            sizes[panel_index] = 0
            sizes[center_index] += current
            self.setSizes(sizes)
        else:
            if current > 1:
                return
            widget.setMinimumWidth(spec["minimum_width"])
            widget.setMaximumWidth(spec["maximum_width"])
            if spec["resizable"]:
                target = max(
                    spec["last_width"], spec["expanded_width"], spec["minimum_width"]
                )
            else:
                target = spec["expanded_width"]
            available = max(0, sizes[center_index] - 260)
            restore = min(target, available) if available else target
            sizes[panel_index] = restore
            sizes[center_index] = max(0, sizes[center_index] - restore)
            self.setSizes(sizes)

        self._enforce_fixed_sides()
        self._position_toggle_strips()
        strip = self._toggle_strips.get(side_name)
        if strip is not None:
            strip.raise_()
            strip.update()
