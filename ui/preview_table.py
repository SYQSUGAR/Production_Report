"""预览表格组件（增强版）—— 支持多选、合并单元格可视化、自定义行高列宽。"""

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QStyledItemDelegate, QStyle,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSignalBlocker
from PyQt6.QtGui import QColor, QFont, QBrush, QPen, QPainter

from models.template_model import TemplateModel, StyleScope, MergeRange, CellData


class BorderDelegate(QStyledItemDelegate):
    """绘制单元格边框的自定义委托。"""

    def paint(self, painter: QPainter, option, index):
        # 先绘制默认内容
        super().paint(painter, option, index)
        # 读取边框数据
        border_data = index.data(Qt.ItemDataRole.UserRole)
        if not border_data:
            return
        top, bottom, left, right, line_style, width, colors = border_data
        width = max(width or 1, 1)
        style_map = {"solid": Qt.PenStyle.SolidLine, "dashed": Qt.PenStyle.DashLine,
                     "dotted": Qt.PenStyle.DotLine, "dash_dot": Qt.PenStyle.DashDotLine,
                     "double": Qt.PenStyle.SolidLine}
        rect = option.rect.adjusted(0, 0, -1, -1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        def draw_side(side_style, color, start, end):
            if not side_style:
                return
            pen = QPen(QColor(color or "#606770"))
            pen.setWidth(width)
            effective_style = side_style if side_style in style_map else line_style
            pen.setStyle(style_map.get(effective_style, Qt.PenStyle.SolidLine))
            painter.setPen(pen)
            painter.drawLine(start, end)
            # Qt 没有原生单元格双线，使用两条平行线模拟。
            if effective_style == "double":
                dx = 0 if start.x() != end.x() else (1 if start.x() == rect.left() else -1)
                dy = 0 if start.y() != end.y() else (1 if start.y() == rect.top() else -1)
                painter.drawLine(start.x() + dx * 2, start.y() + dy * 2,
                                 end.x() + dx * 2, end.y() + dy * 2)

        draw_side(top, colors[0], rect.topLeft(), rect.topRight())
        draw_side(bottom, colors[1], rect.bottomLeft(), rect.bottomRight())
        draw_side(left, colors[2], rect.topLeft(), rect.bottomLeft())
        draw_side(right, colors[3], rect.topRight(), rect.bottomRight())
        painter.restore()




class PreviewTable(QTableWidget):
    """实时渲染模板样式的预览表格。

    信号:
        selection_changed(row, col, scope)  —— 当用户选中单元格/行/列/全表时发出。
        style_applied()                     —— 样式被应用后通知外部刷新面板。
        cells_selected(cells)               —— 多选单元格通知, cells: [(row, col), ...]
    """

    selection_changed = pyqtSignal(int, int, str)  # row, col, scope_name
    style_applied = pyqtSignal()
    cells_selected = pyqtSignal(list)  # [(row,col), ...]
    cell_edited = pyqtSignal(int, int, str)  # row, col, new_text

    def __init__(self, template: TemplateModel, is_admin: bool = True, parent=None):
        super().__init__(parent)
        self._template = template
        self._is_admin = is_admin
        self._data: list[list[str]] = []
        self._init_data()
        self._setup_ui()
        self._connect_signals()
        self.refresh_all()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _init_data(self):
        """构建预览数据：空表格，数据从 template.cell_data 中读取。"""
        rows = self._template.rows
        cols = self._template.cols
        self._data = [["" for _ in range(cols)] for _ in range(rows)]
        # 从 cell_data 同步静态文本
        for (r, c), cd in self._template.cell_data.items():
            if r < rows and c < cols and cd.static_text:
                self._data[r][c] = cd.static_text

    def _setup_ui(self):
        """配置表格外观与行为。"""
        rows, cols = self._template.rows, self._template.cols
        self.setRowCount(rows)
        self.setColumnCount(cols)

        # 设置边框绘制委托
        self.setItemDelegate(BorderDelegate(self))

        # 列头
        self.setHorizontalHeaderLabels([chr(65 + i) for i in range(cols)])
        # 行头
        self.setVerticalHeaderLabels([str(i + 1) for i in range(rows)])

        # 选择行为：支持多选
        if self._is_admin:
            self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # 表头设置
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionsClickable(True)
        vh = self.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vh.setDefaultSectionSize(36)
        vh.setSectionsClickable(True)

        self.setAlternatingRowColors(False)
        # 默认网格线会与自定义边框叠加并掩盖线型，边框完全交给委托绘制。
        self.setShowGrid(False)
        self.setStyleSheet("QTableView::item { border: none; padding: 1px; }")

        # 选中后按任意键即可编辑（类 Excel 行为）
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.AnyKeyPressed
        )

        # 应用自定义行高/列宽
        for r, h in self._template.row_heights.items():
            self.setRowHeight(r, h)
        for c, w in self._template.col_widths.items():
            self.setColumnWidth(c, w)

    def _connect_signals(self):
        """连接选择变更信号。"""
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemChanged.connect(self._on_item_changed)
        self.horizontalHeader().sectionClicked.connect(self._on_column_header_clicked)
        self.verticalHeader().sectionClicked.connect(self._on_row_header_clicked)

    # ------------------------------------------------------------------
    # 编辑事件
    # ------------------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem):
        """双击编辑完成后同步到模板。"""
        row, col = item.row(), item.column()
        text = item.text()
        cd = self._template.get_cell_data(row, col)
        cd.static_text = text
        self._template.set_cell_data(row, col, cd)
        self.cell_edited.emit(row, col, text)

    # ------------------------------------------------------------------
    # 选择事件
    # ------------------------------------------------------------------
    def _on_selection_changed(self):
        """多选/单选变更时通知外部。"""
        indexes = self.selectedIndexes()
        if not indexes:
            return

        # 收集所有选中的单元格
        cells = [(idx.row(), idx.column()) for idx in indexes]
        self.cells_selected.emit(cells)

        # 判断是整列选择还是整行选择
        if self.selectionModel().selectedColumns():
            col = self.selectionModel().selectedColumns()[0].column()
            self.selection_changed.emit(-1, col, "column")
        elif self.selectionModel().selectedRows():
            row = self.selectionModel().selectedRows()[0].row()
            self.selection_changed.emit(row, -1, "row")
        else:
            idx = indexes[0]
            self.selection_changed.emit(idx.row(), idx.column(), "cell")

    def _on_column_header_clicked(self, col: int):
        self.selectColumn(col)
        self.selection_changed.emit(-1, col, "column")

    def _on_row_header_clicked(self, row: int):
        self.selectRow(row)
        self.selection_changed.emit(row, -1, "row")

    def select_default(self):
        """选中"默认/全局"样式。"""
        self.clearSelection()
        self.selection_changed.emit(-1, -1, "default")

    def get_selected_cells(self) -> list[tuple[int, int]]:
        """获取所有选中的单元格坐标列表。"""
        return [(idx.row(), idx.column()) for idx in self.selectedIndexes()]

    # ------------------------------------------------------------------
    # 样式管理 (写给 StylePanel 调用)
    # ------------------------------------------------------------------
    def get_current_scope_info(self) -> tuple[str, int, int]:
        """返回当前选中的 scope 信息: (scope_name, row, col)。"""
        indexes = self.selectedIndexes()
        if not indexes:
            return "default", -1, -1

        if self.selectionModel().selectedColumns():
            col = self.selectionModel().selectedColumns()[0].column()
            return "column", -1, col

        if self.selectionModel().selectedRows():
            row = self.selectionModel().selectedRows()[0].row()
            return "row", row, -1

        idx = indexes[0]
        return "cell", idx.row(), idx.column()

    # ------------------------------------------------------------------
    # 刷新渲染
    # ------------------------------------------------------------------
    def refresh_cell(self, row: int, col: int):
        """刷新单个单元格的显示，处理合并单元格。"""
        blocker = QSignalBlocker(self)
        # 检查是否为合并区域中的非主格（被隐藏的单元格）
        mr = self._template.get_merge_range(row, col)
        if mr and not mr.is_top_left(row, col):
            # 非主格隐藏
            item = self.item(row, col)
            if item:
                item.setText("")
            return

        item = self.item(row, col)
        if not item:
            item = QTableWidgetItem()
            self.setItem(row, col, item)

        # 获取文本
        text = ""
        cd = self._template.get_cell_data(row, col)
        if cd.static_text:
            text = cd.static_text
        elif row < len(self._data) and col < len(self._data[0]):
            text = self._data[row][col]

        item.setText(text)

        style = self._template.get_effective_style(row, col)
        self._apply_style_to_item(item, style)
        del blocker

    def refresh_all(self):
        """刷新全部单元格，并重建合并单元格的 span。"""
        self.blockSignals(True)

        # 先清除所有 span
        for r in range(self._template.rows):
            for c in range(self._template.cols):
                self.setSpan(r, c, 1, 1)

        # 应用合并区域
        for mr in self._template.merge_ranges:
            if mr.bottom_row < self._template.rows and mr.right_col < self._template.cols:
                self.setSpan(
                    mr.top_row, mr.left_col,
                    mr.bottom_row - mr.top_row + 1,
                    mr.right_col - mr.left_col + 1,
                )

        # 刷新所有单元格
        for r in range(self._template.rows):
            for c in range(self._template.cols):
                self.refresh_cell(r, c)

        self.blockSignals(False)

    # ------------------------------------------------------------------
    # 将 CellStyle 写到 QTableWidgetItem
    # ------------------------------------------------------------------
    def _apply_style_to_item(self, item: QTableWidgetItem, style):
        font = style.to_qfont()
        item.setFont(font)

        # 组合水平和垂直对齐
        h_align = style.alignment if style.alignment else int(Qt.AlignmentFlag.AlignCenter)
        v_align = style.vertical_alignment if style.vertical_alignment else int(Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(Qt.AlignmentFlag(h_align | v_align))

        bg = style.to_qcolor_bg()
        if bg and bg.isValid():
            item.setBackground(bg)

        fg = style.to_qcolor_fg()
        if fg and fg.isValid():
            item.setForeground(fg)

        # 存储边框数据到 UserRole 供 BorderDelegate 绘制
        has_border = any([style.border_top, style.border_bottom,
                          style.border_left, style.border_right])
        if has_border:
            border_data = (
                style.border_top, style.border_bottom,
                style.border_left, style.border_right,
                style.border_line_style or "solid",
                style.border_width or 1,
                (style.border_top_color, style.border_bottom_color,
                 style.border_left_color, style.border_right_color),
            )
            item.setData(Qt.ItemDataRole.UserRole, border_data)
        else:
            item.setData(Qt.ItemDataRole.UserRole, None)

    # ------------------------------------------------------------------
    # 获取 / 设置数据
    # ------------------------------------------------------------------
    def get_data(self) -> list[list[str]]:
        result = []
        for r in range(self._template.rows):
            row_data = []
            for c in range(self._template.cols):
                cd = self._template.get_cell_data(r, c)
                text = cd.static_text if cd.static_text else ""
                row_data.append(text)
            result.append(row_data)
        return result

    def set_data(self, data: list[list[str]]):
        self._data = [row[:] for row in data]
        self._template.resize(len(data), len(data[0]) if data else 0)
        self.setRowCount(self._template.rows)
        self.setColumnCount(self._template.cols)
        self.setHorizontalHeaderLabels([chr(65 + i) for i in range(self._template.cols)])
        self.setVerticalHeaderLabels([str(i + 1) for i in range(self._template.rows)])
        self.refresh_all()

    def set_cell_text(self, row: int, col: int, text: str):
        """设置单元格文本（写入 template.cell_data）。"""
        cd = self._template.get_cell_data(row, col)
        cd.static_text = text
        self._template.set_cell_data(row, col, cd)
        self.refresh_cell(row, col)

    def batch_set_text(self, cells: list[tuple[int, int]], text: str):
        """批量设置多个单元格的文本。"""
        for row, col in cells:
            self.set_cell_text(row, col, text)

    def set_admin_mode(self, is_admin: bool):
        """切换管理模式/普通查看模式。"""
        self._is_admin = is_admin
        if is_admin:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def sync_grid(self):
        """模板行列数变更后原地更新表格尺寸（不重建 widget）。"""
        rows, cols = self._template.rows, self._template.cols
        self.setRowCount(rows)
        self.setColumnCount(cols)
        self.setHorizontalHeaderLabels([chr(65 + i) for i in range(cols)])
        self.setVerticalHeaderLabels([str(i + 1) for i in range(rows)])
        self._init_data()
        self.verticalHeader().setDefaultSectionSize(36)
        self.horizontalHeader().setDefaultSectionSize(100)
        for r, height in self._template.row_heights.items():
            if r < rows:
                self.setRowHeight(r, height)
        for c, width in self._template.col_widths.items():
            if c < cols:
                self.setColumnWidth(c, width)
        self.refresh_all()

    def set_template(self, template: TemplateModel):
        """替换数据模型引用并刷新表格。"""
        self._template = template
        self.sync_grid()

    @property
    def template(self) -> TemplateModel:
        return self._template
