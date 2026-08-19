"""报表预览页：仅负责输入本次时间参数、生成并查看最终报表。"""

from datetime import datetime

from PyQt6.QtCore import QDate, QDateTime, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QDateEdit, QDateTimeEdit, QSpinBox, QMessageBox, QAbstractItemView,
)

from models.report_context import ReportContext
from models.time_binding import TimeRangeType, TimeMode
from models.template_model import TemplateModel
from ui.preview_table import PreviewTable


class ReportPreviewPage(QWidget):
    """一次具体日报的只读生成与预览页面。

    模板决定内容、布局、合并关系和样式；预览页不允许二次编辑。
    用户只需要填写模板要求的时间参数，然后点击“生成报表”。
    """

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._source_template = editor._template
        self._display_model = TemplateModel.from_dict(self._source_template.to_dict())
        self._build_ui()
        self._scan_time_requirements()

    # ==================================================================
    # UI
    # ==================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        time_grp = QGroupBox("本次报表时间")
        tl = QHBoxLayout(time_grp)
        tl.setContentsMargins(8, 8, 8, 8)
        tl.setSpacing(8)

        self._lbl_day = QLabel("日:")
        self._day = QDateEdit(QDate.currentDate())
        self._day.setCalendarPopup(True)
        self._day.setDisplayFormat("yyyy-MM-dd")
        tl.addWidget(self._lbl_day)
        tl.addWidget(self._day)

        self._lbl_month = QLabel("月:")
        self._month = QDateEdit(QDate.currentDate())
        self._month.setCalendarPopup(True)
        self._month.setDisplayFormat("yyyy-MM")
        tl.addWidget(self._lbl_month)
        tl.addWidget(self._month)

        self._lbl_year = QLabel("年:")
        self._year = QSpinBox()
        self._year.setRange(1900, 2999)
        self._year.setValue(QDate.currentDate().year())
        tl.addWidget(self._lbl_year)
        tl.addWidget(self._year)

        self._lbl_custom = QLabel("自定义:")
        today_start = QDateTime(QDate.currentDate(), QTime(0, 0))
        self._custom_start = QDateTimeEdit(today_start)
        self._custom_start.setCalendarPopup(True)
        self._custom_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._custom_end = QDateTimeEdit(QDateTime.currentDateTime())
        self._custom_end.setCalendarPopup(True)
        self._custom_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        tl.addWidget(self._lbl_custom)
        tl.addWidget(self._custom_start)
        tl.addWidget(QLabel("至"))
        tl.addWidget(self._custom_end)

        tl.addStretch(1)
        self._btn_generate = QPushButton("生成报表")
        self._btn_generate.setMinimumHeight(34)
        self._btn_generate.clicked.connect(self.generate_report)
        tl.addWidget(self._btn_generate)
        root.addWidget(time_grp)

        self._status = QLabel("请设置需要的时间参数，然后点击“生成报表”。")
        self._status.setStyleSheet("color:#666; padding:2px 4px;")
        root.addWidget(self._status)

        self._result_view = PreviewTable(self._display_model, is_admin=False)
        self._result_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self._result_view, 1)

    # ==================================================================
    # 模板同步与时间参数联动
    # ==================================================================
    def _rebuild_display_model(self):
        """从模板重新创建只读展示副本，预览永远不反向修改模板。"""
        self._display_model = TemplateModel.from_dict(self._source_template.to_dict())
        self._result_view.set_template(self._display_model)
        self._result_view.set_query_results({})

    def sync_template(self):
        """同步模板编辑页的最新内容，但不主动执行数据库查询。"""
        if self._source_template is not self._editor._template:
            self._source_template = self._editor._template
        self._rebuild_display_model()
        self._scan_time_requirements()
        self._status.setText("模板已同步。请设置时间参数后点击“生成报表”。")

    def _scan_time_requirements(self):
        """模板未使用或无需用户指定的时间类型在预览中灰化。"""
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

        self._set_time_enabled(self._lbl_day, self._day, needs[TimeRangeType.DAY])
        self._set_time_enabled(self._lbl_month, self._month, needs[TimeRangeType.MONTH])
        self._set_time_enabled(self._lbl_year, self._year, needs[TimeRangeType.YEAR])

        custom_enabled = needs[TimeRangeType.CUSTOM]
        self._lbl_custom.setEnabled(custom_enabled)
        self._custom_start.setEnabled(custom_enabled)
        self._custom_end.setEnabled(custom_enabled)

    @staticmethod
    def _set_time_enabled(label, control, enabled: bool):
        label.setEnabled(enabled)
        control.setEnabled(enabled)

    def _build_context(self) -> ReportContext:
        """冻结一次生成操作使用的统一查询时刻。"""
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

    # ==================================================================
    # 数据库查询与报表生成
    # ==================================================================
    def _ensure_db_connection(self, config_key: str) -> bool:
        handler = self._editor._db_handler
        if handler.is_connected(config_key):
            return True
        config = self._source_template.db_configs.get(config_key)
        if config is None and config_key == "default":
            config = self._source_template.db_configs.get("default")
        return bool(config and handler.connect(config, config_key))

    def generate_report(self):
        """根据本次时间参数执行模板中的查询，并在只读预览中显示最终报表。"""
        if self._source_template is not self._editor._template:
            self._source_template = self._editor._template

        # 每次生成都从模板重新建立展示副本，避免上一次查询结果残留。
        self._rebuild_display_model()
        self._scan_time_requirements()
        context = self._build_context()

        query_count = 0
        success_count = 0
        failed_count = 0
        invalid_time_count = 0

        for (row, col), source_cd in sorted(self._source_template.cell_data.items()):
            qb = source_cd.query_binding
            if not qb or not qb.enabled:
                continue

            query_count += 1
            time_range = None
            if qb.time_binding.enabled:
                time_range = context.resolve(qb.time_binding)
                if time_range is None:
                    invalid_time_count += 1
                    self._set_result_text(row, col, "[时间参数无效]")
                    continue

            sql = qb.build_sql(time_range=time_range)
            if not sql:
                failed_count += 1
                self._set_result_text(row, col, "[查询配置无效]")
                continue

            config_key = qb.db_config_key or "default"
            if not self._ensure_db_connection(config_key):
                failed_count += 1
                self._set_result_text(row, col, "[数据库未连接]")
                continue

            value = self._editor._db_handler.execute_query(sql, config_key)
            if value is None:
                failed_count += 1
                self._set_result_text(row, col, "[查询失败]")
            else:
                success_count += 1
                self._set_result_text(row, col, str(value))

        self._result_view.refresh_all()

        timestamp = context.generated_at.strftime("%Y-%m-%d %H:%M:%S")
        if query_count == 0:
            self._status.setText(f"报表已生成：{timestamp}（模板中没有数据库查询单元格）")
            return

        self._status.setText(
            f"报表已生成：{timestamp} | 查询 {query_count} 个，成功 {success_count} 个，"
            f"失败 {failed_count} 个，时间参数无效 {invalid_time_count} 个"
        )

        if failed_count or invalid_time_count:
            QMessageBox.warning(
                self,
                "报表生成完成但存在异常",
                f"本次共查询 {query_count} 个数据库单元格。\n"
                f"成功：{success_count}\n失败：{failed_count}\n"
                f"时间参数无效：{invalid_time_count}\n\n"
                "异常位置已在预览表格中标记。",
            )

    def _set_result_text(self, row: int, col: int, value: str):
        """只写入预览副本，不修改模板本体。"""
        cd = self._display_model.get_cell_data(row, col)
        cd.static_text = value
        self._display_model.set_cell_data(row, col, cd)
