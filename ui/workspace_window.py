"""应用工作区：全局文件/数据库 + 报表预览/模板编辑。"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QGroupBox,
    QToolBar, QMenuBar, QMenu, QLabel,
)

from models.value_formatter import format_display_value
from ui.main_window import MainWindow
from ui.report_preview_page import ReportPreviewPage
from ui.time_binding_panel import TimeBindingPanel
from ui.editor_side_panels import StyleOnlyPanel, DatabaseBindingPanel
from ui.editor_history import install_editor_history
from ui.collapsible_side_panel import CollapsibleSplitter, SidebarToggleStrip
from ui.workspace_behaviors import WorkspaceFileBehavior


class WorkspaceWindow(QMainWindow):
    """工作区层级：全局“文件/数据库” > “报表预览/模板编辑”。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产报表模板编辑与预览")
        self.resize(1760, 920)

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
        self._prepare_side_panel_headers()

        self._report_preview = ReportPreviewPage(self._editor)

        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self._report_preview, 1)

        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(0)

        self._template_toolbar = self._build_template_toolbar(template_page)
        template_layout.addWidget(self._template_toolbar)

        editor_row = QWidget()
        editor_row_layout = QHBoxLayout(editor_row)
        editor_row_layout.setContentsMargins(0, 0, 0, 0)
        editor_row_layout.setSpacing(0)

        main_splitter = CollapsibleSplitter()

        self._style_group = QGroupBox("字体 / 样式 / 边框")
        style_group_layout = QVBoxLayout(self._style_group)
        style_group_layout.setContentsMargins(4, 6, 4, 4)
        style_group_layout.addWidget(self._style_panel)
        self._style_group.setMinimumWidth(295)
        self._style_group.setMaximumWidth(370)
        main_splitter.addWidget(self._style_group)

        main_splitter.addWidget(self._editor)

        right = QWidget()
        right.setMinimumWidth(400)
        right.setMaximumWidth(550)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._db_group = QGroupBox("数据库绑定与时间条件")
        db_layout = QVBoxLayout(self._db_group)
        db_layout.setContentsMargins(4, 6, 4, 4)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(self._db_panel)
        vertical.addWidget(self._time_panel)
        vertical.setSizes([590, 300])
        vertical.setStretchFactor(0, 1)
        vertical.setStretchFactor(1, 0)
        db_layout.addWidget(vertical)
        right_layout.addWidget(self._db_group)
        main_splitter.addWidget(right)

        main_splitter.setSizes([320, 1030, 450])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        main_splitter.configure_side("left", panel_index=0, expanded_width=320)
        main_splitter.configure_side("right", panel_index=2, expanded_width=450)

        self._left_toggle_strip = SidebarToggleStrip(main_splitter, "left", editor_row)
        main_splitter.register_toggle_strip("left", self._left_toggle_strip)
        self._right_toggle_strip = SidebarToggleStrip(main_splitter, "right", editor_row)
        main_splitter.register_toggle_strip("right", self._right_toggle_strip)

        editor_row_layout.addWidget(self._left_toggle_strip)
        editor_row_layout.addWidget(main_splitter, 1)
        editor_row_layout.addWidget(self._right_toggle_strip)
        template_layout.addWidget(editor_row, 1)
        self._main_splitter = main_splitter
        self._right_panel_container = right

        self._tabs = QTabWidget()
        self._tabs.addTab(preview_page, "报表预览")
        self._tabs.addTab(template_page, "模板编辑")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self._global_menu_bar = self._build_global_menu_bar(workspace)
        workspace_layout.addWidget(self._global_menu_bar)
        workspace_layout.addWidget(self._tabs, 1)
        self.setCentralWidget(workspace)

        self._editor._preview.selection_changed.connect(self._on_editor_selection)
        self._editor._preview.cells_selected.connect(self._on_editor_cells_selected)
        self._style_panel.style_changed.connect(self._editor._on_style_changed)
        self._style_panel.style_transaction.connect(self._editor._undo_mgr.record_batch)

        self._db_panel._chk_db_enabled.stateChanged.connect(self._time_panel.refresh_availability)
        self._db_panel.database_binding_changed.connect(self._on_binding_changed)
        self._db_panel._cmb_table.currentTextChanged.connect(self._sync_time_field_choices)
        self._time_panel.time_binding_changed.connect(self._on_binding_changed)
        self._time_panel.time_binding_changed.connect(self._db_panel.refresh_sql_preview)

        install_editor_history(self._editor, after_change=self._refresh_side_panels)

        self._wire_global_menu_refresh()
        self._file_behavior = WorkspaceFileBehavior(self, self._editor)

        self._tabs.setCurrentIndex(0)
        self._report_preview.sync_template()
        self._sync_time_field_choices()

        self._editor.menuBar().hide()
        for toolbar in self._editor.findChildren(QToolBar):
            if toolbar.windowTitle() == "主工具栏" and toolbar is not self._template_toolbar:
                toolbar.hide()

    def _flatten_toolbox_page(self, panel):
        toolbox = getattr(panel, "_toolbox", None)
        if toolbox is None or toolbox.count() == 0:
            return None
        page = toolbox.widget(0)
        toolbox.removeItem(0)
        panel._main_layout.removeWidget(toolbox)
        toolbox.hide()
        page.setParent(panel._container)
        return page

    def _prepare_side_panel_headers(self):
        style_page = self._flatten_toolbox_page(self._style_panel)
        if style_page is not None:
            self._style_panel._main_layout.insertWidget(1, style_page, 1)

        selection_label = getattr(self._db_panel, "_lbl_scope", None)
        if selection_label is not None and selection_label.parentWidget() is not None:
            selection_label.parentWidget().hide()

        db_page = self._flatten_toolbox_page(self._db_panel)
        if db_page is not None:
            db_title = QLabel("数据库绑定")
            db_title.setStyleSheet(
                "font-weight:bold; font-size:14px; color:#174EA6; "
                "background:#E8F0FE; border-left:3px solid #1A73E8; "
                "padding:6px 8px;"
            )
            self._db_panel._main_layout.insertWidget(0, db_title)
            self._db_panel._main_layout.insertWidget(1, db_page, 1)

        for label in self._time_panel.findChildren(QLabel):
            if label.text() == "时间绑定":
                label.setStyleSheet(
                    "font-weight:bold; font-size:14px; color:#8A4B08; "
                    "background:#FFF4E5; border-left:3px solid #F29900; "
                    "padding:6px 8px;"
                )
                break

    def _source_global_menus(self):
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
        bar = QMenuBar(parent)
        bar.setObjectName("globalWorkspaceMenuBar")
        bar.setNativeMenuBar(False)

        self._act_refresh_database = None
        for source_menu in self._source_global_menus():
            menu = QMenu(source_menu.title(), bar)
            for action in source_menu.actions():
                menu.addAction(action)

            clean = source_menu.title().replace("&", "")
            if clean.startswith("数据库"):
                menu.addSeparator()
                self._act_refresh_database = QAction("刷新数据库", self)
                self._act_refresh_database.setToolTip("重新读取当前数据库的数据表和字段")
                self._act_refresh_database.triggered.connect(self._refresh_database_metadata)
                menu.addAction(self._act_refresh_database)
            bar.addMenu(menu)
        return bar

    def _refresh_database_metadata(self):
        ok = self._db_panel.refresh_database_metadata()
        self._sync_time_field_choices()
        self._editor._status_label.setText("数据库已刷新" if ok else "未读取到数据库")

    def _sync_time_field_choices(self, *_args):
        table_text = self._db_panel._cmb_table.currentText().strip()
        table = table_text.split()[0] if table_text else ""
        fields = self._db_panel._db_metadata.get(table, [])
        self._time_panel.set_field_choices(fields)

    def _build_template_toolbar(self, parent: QWidget) -> QToolBar:
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

    def _iter_leaf_actions(self, menu: QMenu):
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                yield from self._iter_leaf_actions(submenu)
            elif not action.isSeparator():
                yield action

    def _wire_global_menu_refresh(self):
        for menu in self._source_global_menus():
            for action in self._iter_leaf_actions(menu):
                if action.property("workspace_global_refresh_connected"):
                    continue
                action.triggered.connect(self._schedule_global_refresh)
                action.setProperty("workspace_global_refresh_connected", True)

    def _schedule_global_refresh(self, *_args):
        QTimer.singleShot(0, self._refresh_after_global_action)

    def _refresh_after_global_action(self):
        self._wire_global_menu_refresh()
        if hasattr(self, "_file_behavior"):
            self._file_behavior.rebuild_guarded_preset_menu()
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
        self._sync_time_field_choices()

    def _refresh_side_panels(self):
        self._sync_side_panel_templates()
        scope, row, col = self._editor._preview.get_current_scope_info()
        cells = self._editor._preview.get_selected_cells()
        self._style_panel.set_selected_cells(cells)
        self._db_panel.set_selected_cells(cells)
        self._time_panel.set_selected_cells(cells)
        self._style_panel.set_current_selection(scope, row, col)
        self._db_panel.set_current_selection(scope, row, col)
        self._sync_time_field_choices()
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
        self._sync_time_field_choices()
        self._time_panel.set_selection(row, col, scope)

    def _protect_time_binding_from_db_panel_refresh(self, panel):
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
