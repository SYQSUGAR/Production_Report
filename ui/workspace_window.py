"""应用工作区：全局文件/数据库 + 报表预览/模板编辑。"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QGroupBox,
    QToolBar, QMenuBar, QMenu,
)

from models.value_formatter import format_display_value
from ui.main_window import MainWindow
from ui.report_preview_page import ReportPreviewPage
from ui.time_binding_panel import TimeBindingPanel
from ui.editor_side_panels import StyleOnlyPanel, DatabaseBindingPanel
from ui.editor_history import install_editor_history


class WorkspaceWindow(QMainWindow):
    """工作区层级：全局“文件/数据库” > “报表预览/模板编辑”。

    文件与数据库决定当前工作区使用的模板和数据源，因此同时影响两个页面；
    撤销、复制、粘贴、合并、行列操作等编辑命令只属于模板编辑页。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1760, 920)

        # MainWindow 继续作为模板编辑核心和命令提供者。
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

        self._report_preview = ReportPreviewPage(self._editor)

        # --------------------------------------------------------------
        # 报表预览页：这里只放预览自身内容，不再重复放“文件/数据库”。
        # --------------------------------------------------------------
        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self._report_preview, 1)

        # --------------------------------------------------------------
        # 模板编辑页：第二排编辑工具栏 + 三栏编辑区。
        # --------------------------------------------------------------
        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(0)

        self._template_toolbar = self._build_template_toolbar(template_page)
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

        # --------------------------------------------------------------
        # 页面层：报表预览 / 模板编辑。
        # --------------------------------------------------------------
        self._tabs = QTabWidget()
        self._tabs.addTab(preview_page, "报表预览")
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # --------------------------------------------------------------
        # 全局层：文件 / 数据库。
        # 视觉和逻辑层级都位于页面页签之上，只保留一份。
        # --------------------------------------------------------------
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        self._global_menu_bar = self._build_global_menu_bar(workspace)
        workspace_layout.addWidget(self._global_menu_bar)
        workspace_layout.addWidget(self._tabs, 1)
        self.setCentralWidget(workspace)

        # 工作区信号
        self._editor._preview.selection_changed.connect(self._on_editor_selection)
        self._editor._preview.cells_selected.connect(self._on_editor_cells_selected)

        self._style_panel.style_changed.connect(self._editor._on_style_changed)
        self._style_panel.style_transaction.connect(self._editor._undo_mgr.record_batch)

        self._db_panel._chk_db_enabled.stateChanged.connect(self._time_panel.refresh_availability)
        self._db_panel.database_binding_changed.connect(self._on_binding_changed)
        self._time_panel.time_binding_changed.connect(self._on_binding_changed)
        self._time_panel.time_binding_changed.connect(self._db_panel.refresh_sql_preview)

        install_editor_history(self._editor, after_change=self._refresh_side_panels)

        # 全局文件/数据库动作执行后，统一刷新两个页面使用的工作区状态。
        self._wire_global_menu_refresh()

        # 默认先进入报表预览。
        self._tabs.setCurrentIndex(0)
        self._report_preview.sync_template()

        # MainWindow 自带菜单/工具栏仅作为 QAction 来源，不再重复显示。
        self._editor.menuBar().hide()
        for toolbar in self._editor.findChildren(QToolBar):
            if toolbar.windowTitle() == "主工具栏" and toolbar is not self._template_toolbar:
                toolbar.hide()

    # ==================================================================
    # 全局第一排：文件 / 数据库
    # ==================================================================
    def _source_global_menus(self):
        """返回 MainWindow 中需要提升为全局能力的菜单；显式排除“编辑”。"""
        result = []
        for action in self._editor.menuBar().actions():
            menu = action.menu()
            if menu is None:
                continue
            clean = (menu.title() or action.text()).replace("&", "")
            if clean.startswith("文件") or clean.startswith("数据库"):
                result.append(menu)
        return result

    def _build_global_menu_bar(self, parent: QWidget) -> QMenuBar:
        """构造工作区唯一的“文件 / 数据库”菜单栏。"""
        bar = QMenuBar(parent)
        bar.setObjectName("globalWorkspaceMenuBar")
        bar.setNativeMenuBar(False)

        for source_menu in self._source_global_menus():
            menu = QMenu(source_menu.title(), bar)
            for action in source_menu.actions():
                menu.addAction(action)
            bar.addMenu(menu)
        return bar

    # ==================================================================
    # 模板页第二排：仅模板编辑使用的工具栏
    # ==================================================================
    def _build_template_toolbar(self, parent: QWidget) -> QToolBar:
        """按 MainWindow 原工具栏顺序复制模板编辑动作。"""
        source_toolbar = None
        for toolbar in self._editor.findChildren(QToolBar):
            if toolbar.windowTitle() == "主工具栏":
                source_toolbar = toolbar
                break

        toolbar = QToolBar("模板编辑工具栏", parent)
        toolbar.setObjectName("templateMainToolBar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        if source_toolbar is not None:
            for action in source_toolbar.actions():
                toolbar.addAction(action)
        return toolbar

    # ==================================================================
    # 全局动作后统一同步两个页面
    # ==================================================================
    def _iter_leaf_actions(self, menu: QMenu):
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                yield from self._iter_leaf_actions(submenu)
            elif not action.isSeparator():
                yield action

    def _wire_global_menu_refresh(self):
        """文件/数据库动作完成后统一刷新工作区；兼容动态重建的预设菜单。"""
        for menu in self._source_global_menus():
            for action in self._iter_leaf_actions(menu):
                if action.property("workspace_global_refresh_connected"):
                    continue
                action.triggered.connect(self._schedule_global_refresh)
                action.setProperty("workspace_global_refresh_connected", True)

    def _schedule_global_refresh(self, *_args):
        # 让原 QAction 的文件/数据库槽先完整执行，再读取最终状态。
        QTimer.singleShot(0, self._refresh_after_global_action)

    def _refresh_after_global_action(self):
        # 文件菜单中的“预设模板”可能被动态重建，先补齐新 QAction 的连接。
        self._wire_global_menu_refresh()

        # 模板编辑侧与当前 editor._template 保持同一真值。
        self._sync_side_panel_templates()

        # 数据库配置可能已经变化，丢弃旧元数据缓存；下次需要时重新读取。
        self._db_panel._db_metadata = {}

        # 报表预览重新克隆当前模板，因此静态数据、查询绑定、数据库配置、
        # 时间规则、样式、合并及尺寸等都会同步到预览页。
        self._report_preview.sync_template()

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
        if index == 0:
            self._report_preview.sync_template()

    def closeEvent(self, event):
        try:
            self._editor.close()
        finally:
            super().closeEvent(event)
