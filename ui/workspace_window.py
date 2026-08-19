"""应用工作区：模板编辑 + 报表预览双页面。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QTabWidget

from ui.main_window import MainWindow
from ui.report_preview_page import ReportPreviewPage
from ui.time_binding_panel import TimeBindingPanel


class WorkspaceWindow(QMainWindow):
    """把原模板编辑器保留为第一工作页，并新增报表预览工作页。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1600, 900)

        self._editor = MainWindow()
        self._time_panel = TimeBindingPanel(self._editor)
        self._protect_time_binding_from_db_panel_refresh()
        self._editor._preview.selection_changed.connect(self._time_panel.set_selection)

        template_page = QWidget()
        template_layout = QHBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._editor)
        splitter.addWidget(self._time_panel)
        splitter.setSizes([1320, 280])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        template_layout.addWidget(splitter)

        self._report_preview = ReportPreviewPage(self._editor)

        self._tabs = QTabWidget()
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.addTab(self._report_preview, "报表预览")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

    def _protect_time_binding_from_db_panel_refresh(self):
        """兼容现有 StylePanel：重建 QueryBinding 时保留新增的 TimeBinding。

        后续若把时间控件正式合并进 StylePanel，可删除这层兼容包装。
        """
        panel = self._editor._style_panel
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
        if index == 1:
            self._report_preview.sync_template()
            self._report_preview.refresh_report()

    def closeEvent(self, event):
        # 原 MainWindow 作为子窗口嵌入后不会自然收到顶层 closeEvent，显式交给它处理。
        try:
            self._editor.close()
        finally:
            super().closeEvent(event)
