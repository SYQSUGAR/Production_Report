"""报表预览页：运行时间参数 + 源模板分屏 + 预览映射编排。"""

from datetime import datetime

from PyQt6.QtCore import QDate, QDateTime, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QDateEdit, QDateTimeEdit, QSpinBox, QSplitter, QMessageBox,
    QAbstractItemView,
)

from models.report_context import ReportContext
from models.time_binding import TimeRangeType, TimeMode
from models.template_model import TemplateModel, CellData
from ui.preview_table import PreviewTable
from ui.style_panel import StylePanel


class ReportPreviewPage(QWidget):
    """一次具体日报的预览与编排。

    预览中的位置只保存“目标单元格 -> 源模板单元格”的引用关系；
    数据刷新时始终回到源模板的 QueryBinding 执行查询。
    """

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._source_template = editor._template
        self._display_model = TemplateModel.from_dict(self._source_template.to_dict())
        self._mapping: dict[tuple[int, int], tuple[int, int]] = {}
        self._source_clipboard: dict | None = None
        self._source_query_results: dict[tuple[int, int], str] = {}
        self._reset_identity_mapping()
        self._build_ui()
        self._scan_time_requirements()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        time_grp = QGroupBox("本次报表时间参数")
        tl = QHBoxLayout(time_grp)

        self._day = QDateEdit(QDate.currentDate())
        self._day.setCalendarPopup(True)
        self._day.setDisplayFormat("yyyy-MM-dd")
        tl.addWidget(QLabel("日:")); tl.addWidget(self._day)

        self._month = QDateEdit(QDate.currentDate())
        self._month.setCalendarPopup(True)
        self._month.setDisplayFormat("yyyy-MM")
        tl.addWidget(QLabel("月:")); tl.addWidget(self._month)

        self._year = QSpinBox()
        self._year.setRange(1900, 2999)
        self._year.setValue(QDate.currentDate().year())
        tl.addWidget(QLabel("年:")); tl.addWidget(self._year)

        self._custom_start = QDateTimeEdit(QDateTime.currentDateTime())
        self._custom_start.setCalendarPopup(True)
        self._custom_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._custom_end = QDateTimeEdit(QDateTime.currentDateTime())
        self._custom_end.setCalendarPopup(True)
        self._custom_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        tl.addWidget(QLabel("自定义:")); tl.addWidget(self._custom_start)
        tl.addWidget(QLabel("至")); tl.addWidget(self._custom_end)

        self._btn_refresh = QPushButton("刷新数据")
        self._btn_refresh.clicked.connect(self.refresh_report)
        tl.addWidget(self._btn_refresh)
        root.addWidget(time_grp)

        bar = QHBoxLayout()
        self._btn_toggle_source = QPushButton("隐藏模板源视图")
        self._btn_toggle_source.clicked.connect(self._toggle_source)
        bar.addWidget(self._btn_toggle_source)
        btn_copy = QPushButton("复制源区域")
        btn_copy.clicked.connect(self._copy_source_region)
        bar.addWidget(btn_copy)
        btn_paste = QPushButton("粘贴映射到预览")
        btn_paste.clicked.connect(self._paste_mapping)
        bar.addWidget(btn_paste)
        btn_clear = QPushButton("清除预览选中展示")
        btn_clear.clicked.connect(self._clear_preview_selection)
        bar.addWidget(btn_clear)
        btn_reset = QPushButton("恢复模板原始布局")
        btn_reset.clicked.connect(self._reset_layout)
        bar.addWidget(btn_reset)
        bar.addStretch(1)
        self._lbl_status = QLabel("预览引用模板；修改预览不会修改模板查询。")
        self._lbl_status.setStyleSheet("color:#666;")
        bar.addWidget(self._lbl_status)
        root.addLayout(bar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        source_box = QWidget()
        sl = QVBoxLayout(source_box)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("源模板（只读，可多选并复制）"))
        self._source_view = PreviewTable(self._source_template, is_admin=False)
        self._source_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._source_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        sl.addWidget(self._source_view, 1)
        self._source_box = source_box
        self._splitter.addWidget(source_box)

        result_box = QWidget()
        rl = QHBoxLayout(result_box)
        rl.setContentsMargins(0, 0, 0, 0)
        result_table_box = QWidget()
        rtl = QVBoxLayout(result_table_box)
        rtl.setContentsMargins(0, 0, 0, 0)
        rtl.addWidget(QLabel("报表预览（内容为模板引用；可修改本次预览的显示文字和样式）"))
        self._result_view = PreviewTable(self._display_model, is_admin=True)
        rtl.addWidget(self._result_view, 1)
        rl.addWidget(result_table_box, 1)

        self._preview_style = StylePanel(self._display_model)
        # 预览只允许改显示样式，不暴露数据库绑定页。
        try:
            if self._preview_style._toolbox.count() > 1:
                self._preview_style._toolbox.removeItem(1)
        except Exception:
            pass
        self._preview_style.style_changed.connect(self._result_view.refresh_all)
        self._result_view.selection_changed.connect(self._preview_style.set_current_selection)
        self._result_view.cells_selected.connect(self._preview_style.set_selected_cells)
        rl.addWidget(self._preview_style)
        self._splitter.addWidget(result_box)
        self._splitter.setSizes([520, 900])
        root.addWidget(self._splitter, 1)

    def sync_template(self):
        """模板编辑页可能加载/新建了另一个 TemplateModel，切回预览时同步。"""
        if self._source_template is self._editor._template:
            self._scan_time_requirements()
            return
        self._source_template = self._editor._template
        self._source_view.set_template(self._source_template)
        self._display_model = TemplateModel.from_dict(self._source_template.to_dict())
        self._result_view.set_template(self._display_model)
        self._preview_style._template = self._display_model
        self._reset_identity_mapping()
        self._scan_time_requirements()
        self._lbl_status.setText("已切换到当前模板并恢复原始预览布局。")

    def _reset_identity_mapping(self):
        self._mapping = {
            (r, c): (r, c)
            for r in range(self._source_template.rows)
            for c in range(self._source_template.cols)
        }

    def _reset_layout(self):
        self._display_model = TemplateModel.from_dict(self._source_template.to_dict())
        self._result_view.set_template(self._display_model)
        self._preview_style._template = self._display_model
        self._reset_identity_mapping()
        self.refresh_report()

    def _toggle_source(self):
        visible = not self._source_box.isVisible()
        self._source_box.setVisible(visible)
        self._btn_toggle_source.setText("隐藏模板源视图" if visible else "显示模板源视图")

    def _scan_time_requirements(self):
        needs = {
            TimeRangeType.DAY: False,
            TimeRangeType.MONTH: False,
            TimeRangeType.YEAR: False,
            TimeRangeType.CUSTOM: False,
        }
        for cd in self._source_template.cell_data.values():
            qb = cd.query_binding
            if not qb or not qb.enabled or not qb.time_binding.enabled:
                continue
            tb = qb.time_binding
            if tb.range_type in (TimeRangeType.DAY, TimeRangeType.MONTH, TimeRangeType.YEAR):
                if tb.mode == TimeMode.SELECTED:
                    needs[tb.range_type] = True
            elif tb.range_type == TimeRangeType.CUSTOM:
                needs[TimeRangeType.CUSTOM] = True

        self._day.setEnabled(needs[TimeRangeType.DAY])
        self._month.setEnabled(needs[TimeRangeType.MONTH])
        self._year.setEnabled(needs[TimeRangeType.YEAR])
        self._custom_start.setEnabled(needs[TimeRangeType.CUSTOM])
        self._custom_end.setEnabled(needs[TimeRangeType.CUSTOM])

    def _build_context(self) -> ReportContext:
        generated_at = datetime.now()
        month_date = self._month.date()
        return ReportContext(
            generated_at=generated_at,
            selected_day=self._day.date().toPyDate(),
            selected_month_year=month_date.year(),
            selected_month=month_date.month(),
            selected_year=self._year.value(),
            custom_start=self._custom_start.dateTime().toPyDateTime(),
            custom_end=self._custom_end.dateTime().toPyDateTime(),
        )

    def _ensure_db_connection(self) -> bool:
        handler = self._editor._db_handler
        if handler.is_connected("default"):
            return True
        config = self._source_template.db_configs.get("default")
        if config:
            return handler.connect(config, "default")
        return False

    def refresh_report(self):
        """统一冻结本次查询时刻，回到模板查询，再将值映射到预览。"""
        self.sync_template()
        context = self._build_context()
        source_results: dict[tuple[int, int], str] = {}
        query_cells = []
        for source in sorted(set(self._mapping.values())):
            cd = self._source_template.get_cell_data(*source)
            qb = cd.query_binding
            if qb and qb.enabled:
                query_cells.append((source, qb))

        connected = True
        if query_cells:
            connected = self._ensure_db_connection()
        if query_cells and not connected:
            QMessageBox.warning(self, "数据库未连接", "当前模板包含数据库查询，但尚未建立 default 数据库连接。")

        for source, qb in query_cells:
            time_range = context.resolve(qb.time_binding) if qb.time_binding.enabled else None
            if qb.time_binding.enabled and time_range is None:
                source_results[source] = "[时间参数无效]"
                continue
            sql = qb.build_sql(time_range=time_range)
            if not sql:
                continue
            value = self._editor._db_handler.execute_query(sql, qb.db_config_key or "default") if connected else None
            source_results[source] = "" if value is None else str(value)

        self._source_query_results = source_results
        self._source_view.set_query_results(source_results)

        target_results: dict[tuple[int, int], str] = {}
        for target, source in self._mapping.items():
            if source in source_results:
                target_results[target] = source_results[source]
        self._result_view.set_query_results(target_results)
        self._lbl_status.setText(
            f"已刷新：{context.generated_at.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"数据库单元格 {len(query_cells)} 个"
        )

    def _copy_source_region(self):
        cells = self._source_view.get_selected_cells()
        if not cells:
            self._lbl_status.setText("请先在左侧源模板中选择区域。")
            return
        min_r = min(r for r, _ in cells); max_r = max(r for r, _ in cells)
        min_c = min(c for _, c in cells); max_c = max(c for _, c in cells)
        self._source_clipboard = {
            "top": min_r, "left": min_c,
            "height": max_r - min_r + 1,
            "width": max_c - min_c + 1,
            "cells": set(cells),
            "merges": [mr for mr in self._source_template.merge_ranges
                       if mr.top_row >= min_r and mr.bottom_row <= max_r
                       and mr.left_col >= min_c and mr.right_col <= max_c],
        }
        self._lbl_status.setText(
            f"已复制源模板区域 {self._cell_name(min_r, min_c)}:{self._cell_name(max_r, max_c)}"
        )

    def _paste_mapping(self):
        if not self._source_clipboard:
            self._lbl_status.setText("请先复制源模板区域。")
            return
        row = self._result_view.currentRow()
        col = self._result_view.currentColumn()
        if row < 0 or col < 0:
            self._lbl_status.setText("请先在右侧预览中选择粘贴左上角。")
            return
        cb = self._source_clipboard
        if row + cb["height"] > self._display_model.rows or col + cb["width"] > self._display_model.cols:
            QMessageBox.warning(self, "无法粘贴", "目标区域超出当前预览表格范围。")
            return

        # 清除目标区域中原有映射和合并；源模板的完整合并块会整体平移。
        for tr in range(row, row + cb["height"]):
            for tc in range(col, col + cb["width"]):
                self._mapping.pop((tr, tc), None)
                self._display_model.remove_merge_range(tr, tc)

        for sr in range(cb["top"], cb["top"] + cb["height"]):
            for sc in range(cb["left"], cb["left"] + cb["width"]):
                if (sr, sc) not in cb["cells"]:
                    continue
                tr = row + sr - cb["top"]
                tc = col + sc - cb["left"]
                self._mapping[(tr, tc)] = (sr, sc)
                source_cd = self._source_template.get_cell_data(sr, sc)
                target_cd = self._display_model.get_cell_data(tr, tc)
                target_cd.static_text = source_cd.static_text
                target_cd.query_binding = None  # 预览只保留引用，不复制查询定义
                self._display_model.set_cell_data(tr, tc, target_cd)
                self._display_model.set_cell_style(tr, tc, self._source_template.get_effective_style(sr, sc))

        for mr in cb["merges"]:
            dr = row - cb["top"]; dc = col - cb["left"]
            self._display_model.add_merge_range(
                mr.top_row + dr, mr.bottom_row + dr,
                mr.left_col + dc, mr.right_col + dc,
            )
        self._result_view.refresh_all()
        self.refresh_report()
        self._lbl_status.setText(
            f"已映射到 {self._cell_name(row, col)}；数据仍来源于源模板。"
        )

    def _clear_preview_selection(self):
        cells = self._result_view.get_selected_cells()
        for r, c in cells:
            self._mapping.pop((r, c), None)
            self._display_model.remove_merge_range(r, c)
            self._display_model.clear_cell_data(r, c)
        self._result_view.set_query_results({
            target: value for target, value in self._result_view._query_results.items()
            if target in self._mapping
        })
        self._result_view.refresh_all()
        self._lbl_status.setText(f"已从本次预览移除 {len(cells)} 个展示位置；源模板未修改。")

    @staticmethod
    def _cell_name(row: int, col: int) -> str:
        name = ""
        n = col + 1
        while n:
            n, rem = divmod(n - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{row + 1}"
