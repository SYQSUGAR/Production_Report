"""应用工作区：报表预览 + 模板编辑双页面。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QGroupBox,
    QToolBar, QMenuBar,
)

from models.value_formatter import format_display_value
from ui.main_window import MainWindow
from ui.report_preview_page import ReportPreviewPage
from ui.time_binding_panel import TimeBindingPanel
from ui.editor_side_panels import StyleOnlyPanel, DatabaseBindingPanel
from ui.editor_history import install_editor_history


class WorkspaceWindow(QMainWindow):
    """一级页签为“报表预览 / 模板编辑”，编辑命令只属于模板页。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1760, 920)

        # MainWindow 仍作为模板编辑核心，保留原来的文件/编辑/数据库命令、
        # 公式栏、表格和状态逻辑；WorkspaceWindow 只重新组织页面层级。
        self._editor = MainWindow()
        self._editor._style_panel.hide()
        self._install_template_query_formatter()

        self._style_panel = StyleOnlyPanel(self._editor._template)
        self._db_panel = DatabaseBindingPanel(
            self._editor._template,
            metadata_provider=self._editor._get_db_metadata,
            undo_manager=self._editor._undo_mgr,
        )
        self._time_panel = TimeBindingPanel(
            self._editor,
            undo_manager=self._editor._undo_mgr,
        )
        self._protect_time_binding_from_db_panel_refresh(self._db_panel)

        # --------------------------------------------------------------
        # 模板编辑页：页签下面依次是“原菜单栏 / 原工具栏 / 三栏编辑区”。
        # 两排操作只存在于该页，因此切到报表预览时完全不会出现。
        # --------------------------------------------------------------
        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(0)

        self._build_template_chrome(template_page)
        template_layout.addWidget(self._template_menu_bar)
        template_layout.addWidget(self._template_toolbar)

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
        main_splitter.setSizes([310, 1030, 430])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        template_layout.addWidget(main_splitter, 1)

        # 报表预览页不放任何模板编辑菜单/工具栏。
        self._report_preview = ReportPreviewPage(self._editor)

        self._editor._preview.selection_changed.connect(self._on_editor_selection)
        self._editor._preview.cells_selected.connect(self._on_editor_cells_selected)

        self._style_panel.style_changed.connect(self._editor._on_style_changed)
        self._style_panel.style_transaction.connect(self._editor._undo_mgr.record_batch)

        self._db_panel._chk_db_enabled.stateChanged.connect(self._time_panel.refresh_availability)
        self._db_panel.database_binding_changed.connect(self._on_binding_changed)
        self._time_panel.time_binding_changed.connect(self._on_binding_changed)
        self._time_panel.time_binding_changed.connect(self._db_panel.refresh_sql_preview)

        install_editor_history(self._editor, after_change=self._refresh_side_panels)

        # 一级页签顺序：先预览，再模板编辑。
        self._tabs = QTabWidget()
        self._tabs.addTab(self._report_preview, "报表预览")
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)
        self._tabs.setCurrentIndex(0)
        self._report_preview.sync_template()

    # ==================================================================
    # 模板编辑页内部两排：菜单栏 + 主工具栏
    # ==================================================================
    def _build_template_chrome(self, parent: QWidget):
        """按 MainWindow 原始顺序复制菜单和工具栏动作到模板页内部。

        QAction 本身仍由 MainWindow 持有，只在模板页增加第二个可视入口，
        不搬动 QMenuBar/QToolBar 本体，因此既保持原顺序，也避免 Qt 所有权问题。
        """
        source_menu = self._editor.menuBar()
        self._template_menu_bar = QMenuBar(parent)
        self._template_menu_bar.setObjectName("templateMenuBar")
        self._template_menu_bar.setNativeMenuBar(False)
        for action in source_menu.actions():
            self._template_menu_bar.addAction(action)
        source_menu.hide()

        source_toolbar = None
        for toolbar in self._editor.findChildren(QToolBar):
            if toolbar.windowTitle() == "主工具栏":
                source_toolbar = toolbar
                break

        self._template_toolbar = QToolBar("主工具栏", parent)
        self._template_toolbar.setObjectName("templateMainToolBar")
        self._template_toolbar.setMovable(False)
        self._template_toolbar.setFloatable(False)
        if source_toolbar is not None:
            # actions() 保持 MainWindow 原工具栏的插入顺序，也包括分隔符。
            for action in source_toolbar.actions():
                self._template_toolbar.addAction(action)
            source_toolbar.hide()

    def _install_template_query_formatter(self):
        table = self._editor._preview
        original_set_query_results = table.set_query_results

        def formatted_set_query_results(results):
            formatted = {}
            for (row, col), value in (results or {}).items():
                style = self._editor._template.get_effective_style(row, col)
                formatted[(row, col)] = format_display_value(value, style.number_format)
            original_set_query_results(formatted)

        table.set_query_results = formatted_set_query_results

    def _sync_side_panel_templates(self):
        template = self._editor._template
        self._style_panel._template = template
        self._db_panel.refresh_template(template)

    def _refresh_side_panels(self):
        """撤销/恢复/粘贴等操作后，从模板真值重新加载左右属性栏。"""
        self._sync_side_panel_templates()
        scope, row, col = self._editor._preview.get_current_scope_info()
        cells = self._editor._preview.get_selected_cells()
        self._style_panel.set_selected_cells(cells)
        self._db_panel.set_selected_cells(cells)
        self._time_panel.set_selected_cells(cells)
        self._style_panel.set_current_selection(scope, row, col)
        self._db_panel.set_current_selection(scope, row, col)
        self._time_panel.set_selection(row, col, scope)
        self._report_preview._scan_time_requirements()

    def _on_binding_changed(self, *_args):
        self._time_panel.refresh_availability()
        self._report_preview._scan_time_requirements()

    def _on_editor_cells_selected(self, cells: list):
        self._sync_side_panel_templates()
        self._style_panel.set_selected_cells(cells)
        self._db_panel.set_selected_cells(cells)
        self._time_panel.set_selected_cells(cells)

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
        # 0 = 报表预览；进入预览时同步当前模板，但不显示任何编辑命令。
        if index == 0:
            self._report_preview.sync_template()

    def closeEvent(self, event):
        try:
            self._editor.close()
        finally:
            super().closeEvent(event)
