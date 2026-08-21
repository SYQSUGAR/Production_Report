"""应用工作区：报表预览 + 模板编辑双页面。"""

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
    """一级页签为“报表预览 / 模板编辑”。

    “文件 / 数据库”属于整个报表工作区，在两个页签中都显示；
    撤销、复制、粘贴、合并、行列操作等只属于模板编辑页。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1760, 920)

        # MainWindow 继续作为模板编辑核心，保留原来的命令、公式栏、表格和状态逻辑。
        # WorkspaceWindow 只重新组织“哪些命令属于全局、哪些只属于模板编辑”。
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

        # 报表预览页先建立，后续全局“文件/数据库”动作可以随时刷新它。
        self._report_preview = ReportPreviewPage(self._editor)

        # --------------------------------------------------------------
        # 报表预览页
        # 第一排：文件 / 数据库（全局）
        # 下面：只读报表预览
        # --------------------------------------------------------------
        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        self._preview_menu_bar = self._build_global_menu_bar(preview_page, "previewGlobalMenuBar")
        preview_layout.addWidget(self._preview_menu_bar)
        preview_layout.addWidget(self._report_preview, 1)

        # --------------------------------------------------------------
        # 模板编辑页
        # 第一排：文件 / 数据库（全局）
        # 第二排：撤销/恢复/复制/粘贴/合并/行列等模板编辑工具
        # 下面：样式 | 模板表格 | 数据库绑定+时间
        # --------------------------------------------------------------
        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(0)

        self._template_menu_bar = self._build_global_menu_bar(
            template_page, "templateGlobalMenuBar"
        )
        template_layout.addWidget(self._template_menu_bar)

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

        # 文件/数据库菜单动作在任何页签执行后，都重新同步当前模板和预览。
        self._wire_global_menu_refresh()

        # 一级页签顺序：先预览，再模板编辑。
        self._tabs = QTabWidget()
        self._tabs.addTab(preview_page, "报表预览")
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)
        self._tabs.setCurrentIndex(0)
        self._report_preview.sync_template()

        # MainWindow 自己的菜单/工具栏只是动作来源，不再在中间编辑器里显示。
        self._editor.menuBar().hide()
        for toolbar in self._editor.findChildren(QToolBar):
            if toolbar.windowTitle() == "主工具栏" and toolbar is not self._template_toolbar:
                toolbar.hide()

    # ==================================================================
    # 第一排：全局“文件 / 数据库”菜单
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

    def _build_global_menu_bar(self, parent: QWidget, object_name: str) -> QMenuBar:
        """构造只包含“文件 / 数据库”的第一排菜单。

        子 QAction 直接复用 MainWindow 原动作，因此文件打开、预设、导入 Excel、
        数据库配置/测试/刷新等行为与原程序完全一致；“编辑”不再重复显示。
        """
        bar = QMenuBar(parent)
        bar.setObjectName(object_name)
        bar.setNativeMenuBar(False)

        for source_menu in self._source_global_menus():
            menu = QMenu(source_menu.title(), bar)
            for action in source_menu.actions():
                menu.addAction(action)
            bar.addMenu(menu)
        return bar

    # ==================================================================
    # 第二排：仅模板编辑使用的工具栏
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
    # 全局动作后同步预览
    # ==================================================================
    def _iter_leaf_actions(self, menu: QMenu):
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                yield from self._iter_leaf_actions(submenu)
            elif not action.isSeparator():
                yield action

    def _wire_global_menu_refresh(self):
        """文件/数据库操作完成后刷新预览；同时给动态重建的预设动作补连接。"""
        for menu in self._source_global_menus():
            for action in self._iter_leaf_actions(menu):
                if action.property("workspace_preview_refresh_connected"):
                    continue
                action.triggered.connect(self._schedule_global_refresh)
                action.setProperty("workspace_preview_refresh_connected", True)

    def _schedule_global_refresh(self, *_args):
        # 原 QAction 的槽先完成（文件对话框/数据库对话框也先结束），
        # 再在事件循环下一拍读取最终 editor._template。
        QTimer.singleShot(0, self._refresh_after_global_action)

    def _refresh_after_global_action(self):
        self._wire_global_menu_refresh()
        self._sync_side_panel_templates()
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
        # 0 = 报表预览；每次进入预览都重新读取当前模板。
        if index == 0:
            self._report_preview.sync_template()

    def closeEvent(self, event):
        try:
            self._editor.close()
        finally:
            super().closeEvent(event)
