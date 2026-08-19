"""应用工作区：模板编辑 + 报表预览双页面。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QGroupBox,
)

from ui.main_window import MainWindow
from ui.report_preview_page import ReportPreviewPage
from ui.time_binding_panel import TimeBindingPanel
from ui.editor_side_panels import StyleOnlyPanel, DatabaseBindingPanel


class WorkspaceWindow(QMainWindow):
    """模板编辑采用“样式 | 表格 | 数据库+时间”三栏结构。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1760, 920)

        self._editor = MainWindow()
        # MainWindow 原来的 StylePanel 保留作为内部兼容对象，但不再占界面位置。
        self._editor._style_panel.hide()

        self._style_panel = StyleOnlyPanel(self._editor._template)
        self._db_panel = DatabaseBindingPanel(
            self._editor._template,
            metadata_provider=self._editor._get_db_metadata,
        )
        self._time_panel = TimeBindingPanel(self._editor)
        self._protect_time_binding_from_db_panel_refresh(self._db_panel)

        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._style_panel)
        main_splitter.addWidget(self._editor)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        db_group = QGroupBox("数据库绑定与时间条件")
        db_layout = QVBoxLayout(db_group)
        db_layout.setContentsMargins(4, 4, 4, 4)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(self._db_panel)
        vertical.addWidget(self._time_panel)
        vertical.setSizes([590, 300])
        vertical.setStretchFactor(0, 1)
        vertical.setStretchFactor(1, 0)
        db_layout.addWidget(vertical)
        right_layout.addWidget(db_group)

        main_splitter.addWidget(right)
        main_splitter.setSizes([310, 1030, 420])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        template_layout.addWidget(main_splitter)

        self._report_preview = ReportPreviewPage(self._editor)

        # 当前单元格选择同时驱动左右两栏。
        self._editor._preview.selection_changed.connect(self._on_editor_selection)
        self._editor._preview.cells_selected.connect(self._on_editor_cells_selected)

        # 外置样式栏直接修改同一 TemplateModel，并复用编辑器原撤销栈/表格刷新。
        self._style_panel.style_changed.connect(self._editor._on_style_changed)
        self._style_panel.style_transaction.connect(self._editor._undo_mgr.record_batch)

        # 数据库开关决定时间绑定是否可用。
        self._db_panel._chk_db_enabled.stateChanged.connect(self._time_panel.refresh_availability)
        self._db_panel._chk_db_enabled.stateChanged.connect(
            lambda *_: self._report_preview._scan_time_requirements()
        )

        # 时间规则一变，SQL 模板和预览时间输入都立即更新。
        self._time_panel.time_binding_changed.connect(self._db_panel.refresh_sql_preview)
        self._time_panel.time_binding_changed.connect(self._report_preview._scan_time_requirements)

        self._tabs = QTabWidget()
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.addTab(self._report_preview, "报表预览")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

    def _sync_side_panel_templates(self):
        template = self._editor._template
        self._style_panel._template = template
        self._db_panel.refresh_template(template)

    def _on_editor_cells_selected(self, cells: list):
        self._sync_side_panel_templates()
        self._style_panel.set_selected_cells(cells)
        self._db_panel.set_selected_cells(cells)

    def _on_editor_selection(self, row: int, col: int, scope: str):
        self._sync_side_panel_templates()
        self._style_panel.set_current_selection(scope, row, col)
        self._db_panel.set_current_selection(scope, row, col)
        self._time_panel.set_selection(row, col, scope)

    def _protect_time_binding_from_db_panel_refresh(self, panel):
        """数据库查询控件重建 QueryBinding 时保留当前时间规则。"""
        original = getattr(panel, "_collect_db_binding", None)
        if original is None:
            return

        def wrapped_collect():
            row = getattr(panel, "_current_row", -1)
            col = getattr(panel, "_current_col", -1)
            old_binding = None
            if row >= 0 and col >= 0:
                old_binding = self._editor._template.get_cell_data(row, col).query_binding
            new_binding = original()
            if old_binding is not None and hasattr(old_binding, "time_binding"):
                new_binding.time_binding = old_binding.time_binding
            return new_binding

        panel._collect_db_binding = wrapped_collect

    def _on_tab_changed(self, index: int):
        self._sync_side_panel_templates()
        if index == 1:
            # 进入预览只同步模板；点击“生成报表”时才执行数据库查询。
            self._report_preview.sync_template()

    def closeEvent(self, event):
        try:
            self._editor.close()
        finally:
            super().closeEvent(event)
