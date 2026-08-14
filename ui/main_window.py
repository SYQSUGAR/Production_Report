"""主窗口 —— 完整工具栏 + 公式栏 + 预览表格 + 属性面板。"""

import os
import shutil
from datetime import date

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QLabel, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QInputDialog, QDateEdit, QComboBox, QFontComboBox,
    QSpinBox, QColorDialog, QPushButton, QToolButton, QSlider,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QSettings
from PyQt6.QtGui import QAction, QColor, QFont

from models.template_model import TemplateModel, CellStyle, CellData, StyleScope
from models.user_model import UserRole, UserSession
from models.db_config import DbConfig, QueryBinding, QueryType
from ui.preview_table import PreviewTable
from ui.style_panel import StylePanel
from ui.formula_bar import FormulaBar
from export.excel_exporter import ExcelExporter
from export.template_io import TemplateIO
from export.excel_importer import ExcelImporter
from database.db_handler import DbHandler
from templates.presets import BUILTIN_TEMPLATES

# 应用数据目录
_APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".report_editor")
os.makedirs(_APP_DATA_DIR, exist_ok=True)
_SESSION_FILE = os.path.join(_APP_DATA_DIR, "last_session.json")
_DEFAULT_TEMPLATE_FILE = os.path.join(_APP_DATA_DIR, "default_template.json")
_DEFAULT_BACKUP_FILE = os.path.join(_APP_DATA_DIR, "default_template_backup.json")


class _DbConfigDialog(QDialog):
    """数据库连接配置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据库连接配置")
        self.setFixedSize(400, 320)

        layout = QFormLayout(self)

        self._cmb_type = QComboBox()
        self._cmb_type.addItems(["mysql", "sqlserver"])
        layout.addRow("数据库类型:", self._cmb_type)

        self._txt_host = QLineEdit("localhost")
        layout.addRow("主机地址:", self._txt_host)

        self._spn_port = QSpinBox()
        self._spn_port.setRange(0, 65535)
        self._spn_port.setValue(3306)
        layout.addRow("端口:", self._spn_port)

        self._txt_user = QLineEdit("root")
        layout.addRow("用户名:", self._txt_user)

        self._txt_password = QLineEdit()
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("密码:", self._txt_password)

        self._txt_database = QLineEdit()
        layout.addRow("数据库名:", self._txt_database)

        self._txt_charset = QLineEdit("utf8mb4")
        layout.addRow("字符集:", self._txt_charset)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def get_config(self) -> DbConfig:
        return DbConfig(
            db_type=self._cmb_type.currentText(),
            host=self._txt_host.text(),
            port=self._spn_port.value(),
            user=self._txt_user.text(),
            password=self._txt_password.text(),
            database=self._txt_database.text(),
            charset=self._txt_charset.text(),
        )


class _UndoManager:
    """管理撤销/恢复栈，支持批量操作（文本 + 样式）。

    一个撤销条目是一组 change，每个 change 是元组：
        ("text",  row, col, old_text, new_text)
        ("style", row, col, old_style, new_style)
    批量操作（如粘贴、批量赋值）只占一个撤销条目，撤销/恢复时整体执行。
    """

    def __init__(self):
        self._undo_stack: list[list[tuple]] = []
        self._redo_stack: list[list[tuple]] = []
        self._editing_cell: tuple | None = None
        self._start_text: str = ""
        self._latest_text: str = ""

    def start_edit(self, row: int, col: int, current_text: str):
        """开始编辑一个单元格，若之前有未提交的编辑则先提交。"""
        if self._editing_cell is not None:
            self._commit()
        self._editing_cell = (row, col)
        self._start_text = current_text
        self._latest_text = current_text

    def update_edit(self, text: str):
        """记录编辑过程中的最新文本（不推入栈）。"""
        self._latest_text = text

    def record_text(self, row: int, col: int, old: str, new: str):
        """记录一次已完成的单个单元格文本变更。"""
        self._commit()
        if old == new:
            return
        self._undo_stack.append([("text", row, col, old, new)])
        self._redo_stack.clear()

    def record_change(self, row: int, col: int, old: str, new: str):
        """兼容旧调用名称。"""
        self.record_text(row, col, old, new)

    def record_batch(self, changes: list[tuple]):
        """记录一次批量变更（可混合文本/样式），作为一个撤销单元。"""
        self._commit()
        if not changes:
            return
        self._undo_stack.append(list(changes))
        self._redo_stack.clear()

    def _commit(self):
        """将当前编辑批次（单个单元格连续输入）推入撤销栈。"""
        if self._editing_cell is None:
            return
        if self._latest_text != self._start_text:
            r, c = self._editing_cell
            self._undo_stack.append([("text", r, c, self._start_text, self._latest_text)])
            self._redo_stack.clear()
        self._editing_cell = None

    def undo(self) -> list[tuple] | None:
        """撤销一步，返回该步的 change 列表。"""
        self._commit()
        if not self._undo_stack:
            return None
        changes = self._undo_stack.pop()
        self._redo_stack.append(changes)
        return changes

    def redo(self) -> list[tuple] | None:
        """恢复一步，返回该步的 change 列表。"""
        self._commit()
        if not self._redo_stack:
            return None
        changes = self._redo_stack.pop()
        self._undo_stack.append(changes)
        return changes

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._editing_cell = None


class MainWindow(QMainWindow):
    """桌面端可视化报表模板编辑器主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("可视化报表模板编辑器")

        # 持久化设置
        self._settings = QSettings("ReportEditor", "TemplateEditor")
        self._last_directory = self._settings.value("last_directory",
                                                     os.path.expanduser("~\\Desktop"))

        # 恢复窗口几何
        geo = self._settings.value("window_geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1400, 850)

        # 用户会话
        self._session = UserSession(UserRole.ADMIN)

        # 数据库处理器
        self._db_handler = DbHandler()

        # 数据模型
        self._template = TemplateModel(rows=30, cols=10)

        # 撤销管理器
        self._undo_mgr = _UndoManager()

        # 内部剪贴板（复制/粘贴）
        self._clipboard: dict | None = None
        self._clipboard_system_text: str = ""
        # 格式剪贴板（格式拷贝/格式粘贴，独立于普通复制）
        self._format_clipboard: dict | None = None

        # 当前打开的文件路径
        self._current_filepath: str = ""

        # UI 组件
        self._formula_bar = FormulaBar()
        self._preview = PreviewTable(self._template, is_admin=True)
        self._style_panel = StylePanel(self._template, metadata_provider=self._get_db_metadata)

        self._setup_menu()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._connect_signals()

        # 尝试恢复上次会话
        self._restore_last_session()

    # ==================================================================
    # 菜单栏
    # ==================================================================
    def _setup_menu(self):
        mb = self.menuBar()

        # 文件菜单
        file_menu = mb.addMenu("文件(&F)")

        act_new = QAction("新建模板(&N)", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._new_template)
        file_menu.addAction(act_new)

        self._preset_menu = QMenu("加载预设模板", self)
        file_menu.addMenu(self._preset_menu)
        self._rebuild_preset_menu()

        # 预设管理子菜单
        self._preset_mgmt_menu = QMenu("预设模板管理", self)
        file_menu.addMenu(self._preset_mgmt_menu)

        act_save_as_preset = QAction("将当前模板保存为预设...", self)
        act_save_as_preset.triggered.connect(self._save_as_preset)
        self._preset_mgmt_menu.addAction(act_save_as_preset)

        act_import_preset = QAction("从JSON导入预设...", self)
        act_import_preset.triggered.connect(self._import_preset)
        self._preset_mgmt_menu.addAction(act_import_preset)

        self._preset_mgmt_menu.addSeparator()

        act_del_preset = QAction("删除自定义预设...", self)
        act_del_preset.triggered.connect(self._delete_preset)
        self._preset_mgmt_menu.addAction(act_del_preset)

        file_menu.addSeparator()

        act_load = QAction("打开模板(&O)...", self)
        act_load.setShortcut("Ctrl+O")
        act_load.triggered.connect(self._load_template)
        file_menu.addAction(act_load)

        act_save = QAction("保存模板(&S)", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_template)
        file_menu.addAction(act_save)

        act_save_as = QAction("另存模板(&A)...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._save_as_template)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_import = QAction("导入 Excel(&I)...", self)
        act_import.triggered.connect(self._import_excel)
        file_menu.addAction(act_import)

        act_export = QAction("导出 Excel(&E)...", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._export_excel)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_set_default = QAction("设置默认模板...", self)
        act_set_default.triggered.connect(self._set_default_template)
        file_menu.addAction(act_set_default)

        act_restore_default = QAction("恢复默认模板", self)
        act_restore_default.triggered.connect(self._restore_default_template)
        file_menu.addAction(act_restore_default)

        file_menu.addSeparator()

        act_reset = QAction("重置模板(&R)...", self)
        act_reset.triggered.connect(self._reset_template)
        file_menu.addAction(act_reset)

        # 编辑菜单
        edit_menu = mb.addMenu("编辑(&E)")

        act_undo = QAction("撤销(&Z)", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.triggered.connect(self._undo)
        edit_menu.addAction(act_undo)

        act_redo = QAction("恢复(&Y)", self)
        act_redo.setShortcut("Ctrl+Y")
        act_redo.triggered.connect(self._redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()

        act_copy = QAction("复制(&C)", self)
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self._copy)
        edit_menu.addAction(act_copy)

        act_paste = QAction("粘贴(&V)", self)
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self._paste)
        edit_menu.addAction(act_paste)

        act_paste_values = QAction("仅粘贴内容", self)
        act_paste_values.triggered.connect(self._paste_values)
        edit_menu.addAction(act_paste_values)

        act_copy_format = QAction("格式拷贝(&F)", self)
        act_copy_format.setShortcut("Ctrl+Shift+C")
        act_copy_format.triggered.connect(self._copy_format)
        edit_menu.addAction(act_copy_format)

        act_paste_format = QAction("格式粘贴(&P)", self)
        act_paste_format.setShortcut("Ctrl+Shift+V")
        act_paste_format.triggered.connect(self._paste_format)
        edit_menu.addAction(act_paste_format)

        edit_menu.addSeparator()

        act_merge = QAction("合并单元格(&M)", self)
        act_merge.setShortcut("Ctrl+M")
        act_merge.triggered.connect(self._merge_cells)
        edit_menu.addAction(act_merge)

        act_unmerge = QAction("取消合并(&U)", self)
        act_unmerge.triggered.connect(self._unmerge_cells)
        edit_menu.addAction(act_unmerge)

        edit_menu.addSeparator()

        act_insert_row = QAction("插入行", self)
        act_insert_row.triggered.connect(self._insert_row)
        edit_menu.addAction(act_insert_row)

        act_delete_row = QAction("删除行", self)
        act_delete_row.triggered.connect(self._delete_row)
        edit_menu.addAction(act_delete_row)

        act_insert_col = QAction("插入列", self)
        act_insert_col.triggered.connect(self._insert_column)
        edit_menu.addAction(act_insert_col)

        act_delete_col = QAction("删除列", self)
        act_delete_col.triggered.connect(self._delete_column)
        edit_menu.addAction(act_delete_col)

        # 数据库菜单
        db_menu = mb.addMenu("数据库(&D)")

        act_db_config = QAction("数据库连接配置...", self)
        act_db_config.triggered.connect(self._db_config)
        db_menu.addAction(act_db_config)

        act_db_test = QAction("测试连接", self)
        act_db_test.triggered.connect(self._db_test_connect)
        db_menu.addAction(act_db_test)

        act_refresh = QAction("刷新查询结果", self)
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(self._refresh_query_results)
        db_menu.addAction(act_refresh)

    # ==================================================================
    # 工具栏
    # ==================================================================
    def _setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        # 撤销 / 恢复
        act_undo = QAction("撤销", self)
        act_undo.setToolTip("撤销 (Ctrl+Z)")
        act_undo.triggered.connect(self._undo)
        tb.addAction(act_undo)

        act_redo = QAction("恢复", self)
        act_redo.setToolTip("恢复 (Ctrl+Y)")
        act_redo.triggered.connect(self._redo)
        tb.addAction(act_redo)

        tb.addSeparator()

        act_copy = QAction("复制", self)
        act_copy.setToolTip("复制 (Ctrl+C)")
        act_copy.triggered.connect(self._copy)
        tb.addAction(act_copy)

        act_paste = QAction("粘贴", self)
        act_paste.setToolTip("粘贴 (Ctrl+V)")
        act_paste.triggered.connect(self._paste)
        tb.addAction(act_paste)

        act_copy_format = QAction("格式拷贝", self)
        act_copy_format.setToolTip("格式拷贝 (Ctrl+Shift+C)")
        act_copy_format.triggered.connect(self._copy_format)
        tb.addAction(act_copy_format)

        act_paste_format = QAction("格式粘贴", self)
        act_paste_format.setToolTip("格式粘贴 (Ctrl+Shift+V)")
        act_paste_format.triggered.connect(self._paste_format)
        tb.addAction(act_paste_format)

        tb.addSeparator()

        act_merge = QAction("合并", self)
        act_merge.triggered.connect(self._merge_cells)
        tb.addAction(act_merge)

        act_unmerge = QAction("取消合并", self)
        act_unmerge.triggered.connect(self._unmerge_cells)
        tb.addAction(act_unmerge)

        tb.addSeparator()

        act_add_row = QAction("+行", self)
        act_add_row.triggered.connect(self._insert_row)
        tb.addAction(act_add_row)

        act_del_row = QAction("-行", self)
        act_del_row.triggered.connect(self._delete_row)
        tb.addAction(act_del_row)

        act_add_col = QAction("+列", self)
        act_add_col.triggered.connect(self._insert_column)
        tb.addAction(act_add_col)

        act_del_col = QAction("-列", self)
        act_del_col.triggered.connect(self._delete_column)
        tb.addAction(act_del_col)

        tb.addSeparator()

        act_export = QAction("导出 Excel", self)
        act_export.triggered.connect(self._export_excel)
        tb.addAction(act_export)

    # ==================================================================
    # 中央布局
    # ==================================================================
    def _setup_central(self):
        """公式栏 + 预览表格 | 属性面板。"""
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 公式栏
        main_layout.addWidget(self._formula_bar)

        # 左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._style_panel)
        splitter.addWidget(self._preview)
        splitter.setSizes([300, 1080])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

    # ==================================================================
    # 状态栏
    # ==================================================================
    def _setup_statusbar(self):
        self._status_label = QLabel("就绪 — 管理员模式 | 点击单元格开始编辑")
        self.statusBar().addWidget(self._status_label, 1)

        # 缩放控件（类 Excel）
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(40)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(50, 200)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._zoom_slider.setTickInterval(50)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self.statusBar().addPermanentWidget(self._zoom_slider)
        self.statusBar().addPermanentWidget(self._zoom_label)

    # ==================================================================
    # 信号连接
    # ==================================================================
    def _connect_signals(self):
        # 预览表格选中变化 → 面板 + 公式栏
        self._preview.selection_changed.connect(self._on_selection_changed)
        self._preview.cells_selected.connect(self._on_cells_selected)
        self._preview.cell_edited.connect(self._on_cell_edited)
        self._preview.copy_requested.connect(self._copy)
        self._preview.paste_requested.connect(self._paste)
        self._preview.undo_requested.connect(self._undo)
        self._preview.redo_requested.connect(self._redo)

        # 样式面板变更 → 刷新预览
        self._style_panel.style_changed.connect(self._on_style_changed)
        self._style_panel.style_transaction.connect(self._undo_mgr.record_batch)

        # 公式栏内容变更
        self._formula_bar.content_changed.connect(self._on_formula_content_changed)
        self._formula_bar.batch_apply.connect(self._on_batch_apply)

        # 缩放信号
        self._preview.zoom_changed.connect(self._on_preview_zoom_changed)

    # ==================================================================
    # 槽函数
    # ==================================================================
    def _on_selection_changed(self, row: int, col: int, scope: str):
        self._style_panel.set_current_selection(scope, row, col)
        # 更新公式栏 + 记录撤销起点
        if row >= 0 and col >= 0:
            cd = self._template.get_cell_data(row, col)
            text = cd.static_text if cd.static_text else ""
            self._formula_bar.set_current_cell(row, col, text)
            self._undo_mgr.start_edit(row, col, text)
        else:
            self._formula_bar.set_current_cell(row, col, "")

        parts = {
            "cell": f"单元格 ({row + 1}, {chr(65 + col)})",
            "row": f"第 {row + 1} 行",
            "column": f"列 {chr(65 + col)}",
            "default": "全局默认样式",
        }
        desc = parts.get(scope, "—")
        self._status_label.setText(f"当前选中: {desc}")

    def _on_cells_selected(self, cells: list):
        """多选单元格时更新公式栏和样式面板。"""
        self._style_panel.set_selected_cells(cells)
        if cells:
            row, col = cells[-1]
            cd = self._template.get_cell_data(row, col)
            text = cd.static_text if cd.static_text else ""
            self._formula_bar.set_current_cell(row, col, text)

    def _on_cell_edited(self, row: int, col: int, text: str):
        """双击单元格编辑完成 → 同步公式栏。"""
        old = self._formula_bar.get_content() if (
            self._formula_bar._current_row == row and self._formula_bar._current_col == col
        ) else ""
        self._undo_mgr.record_text(row, col, old, text)
        self._formula_bar.set_current_cell(row, col, text)

    def _on_style_changed(self):
        selected = self._preview.get_selected_cells()
        current = (self._preview.currentRow(), self._preview.currentColumn())
        self._preview.refresh_all()
        self._preview.select_cells(selected, current)

    def _on_zoom_slider_changed(self, value: int):
        """底部缩放滑块变更 → 更新表格。"""
        self._preview.set_zoom(value)
        self._zoom_label.setText(f"{value}%")

    def _on_preview_zoom_changed(self, zoom: int):
        """Ctrl+滚轮缩放 → 同步滑块。"""
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(zoom)
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{zoom}%")

    def _on_formula_content_changed(self, row: int, col: int, text: str):
        """公式栏文本变更 → 更新单元格数据。"""
        cd = self._template.get_cell_data(row, col)
        old = cd.static_text
        cd.static_text = text
        self._template.set_cell_data(row, col, cd)
        self._preview.refresh_cell(row, col)
        self._undo_mgr.record_text(row, col, old, text)

    def _on_batch_apply(self, text: str):
        """批量赋值到选中的多个单元格（作为一个撤销单元）。"""
        cells = self._preview.get_selected_cells()
        changes = []
        for row, col in cells:
            old = self._template.get_cell_data(row, col).static_text
            self._preview.set_cell_text(row, col, text)
            if old != text:
                changes.append(("text", row, col, old, text))
        self._undo_mgr.record_batch(changes)
        self._status_label.setText(f"已批量赋值 {len(cells)} 个单元格")

    # ==================================================================
    # 撤销 / 恢复
    # ==================================================================
    def _apply_undo_change(self, change: tuple, use_new: bool):
        """应用/回滚一个 change。use_new=True 应用新值，False 恢复旧值。"""
        kind = change[0]
        if kind == "text":
            _, row, col, old, new = change
            text = new if use_new else old
            cd = self._template.get_cell_data(row, col)
            cd.static_text = text
            self._template.set_cell_data(row, col, cd)
            if self._formula_bar._current_row == row and self._formula_bar._current_col == col:
                self._formula_bar.set_current_cell(row, col, text)
        elif kind == "style":
            _, row, col, old_style, new_style = change
            style = new_style if use_new else old_style
            if style is None:
                self._template.clear_cell_style(row, col)
            else:
                self._template.set_cell_style(row, col, style)
            self._preview.refresh_cell(row, col)
        elif kind == "row_style":
            _, row, old, new = change
            style = new if use_new else old
            if style is None: self._template.clear_row_style(row)
            else: self._template.set_row_style(row, style)
        elif kind == "column_style":
            _, col, old, new = change
            style = new if use_new else old
            if style is None: self._template.clear_column_style(col)
            else: self._template.set_column_style(col, style)
        elif kind == "default_style":
            _, old, new = change
            self._template.default_style = (new if use_new else old).clone()
        elif kind == "merges":
            _, old, new = change
            self._template.merge_ranges = set(new if use_new else old)

    def _undo(self):
        """撤销一步（若为批量操作则整体撤销）。"""
        changes = self._undo_mgr.undo()
        if changes is None:
            self._status_label.setText("没有可撤销的操作")
            return
        if len(changes) == 1 and changes[0][0] == "structure":
            self._restore_template_dict(changes[0][1])
            self._status_label.setText("已撤销")
            return
        selected = self._preview.get_selected_cells()
        current = (self._preview.currentRow(), self._preview.currentColumn())
        for change in reversed(changes):
            self._apply_undo_change(change, use_new=False)
        self._preview.refresh_all()
        self._preview.select_cells(selected, current)
        self._status_label.setText("已撤销")

    def _redo(self):
        """恢复一步（若为批量操作则整体恢复）。"""
        changes = self._undo_mgr.redo()
        if changes is None:
            self._status_label.setText("没有可恢复的操作")
            return
        if len(changes) == 1 and changes[0][0] == "structure":
            self._restore_template_dict(changes[0][2])
            self._status_label.setText("已恢复")
            return
        selected = self._preview.get_selected_cells()
        current = (self._preview.currentRow(), self._preview.currentColumn())
        for change in changes:
            self._apply_undo_change(change, use_new=True)
        self._preview.refresh_all()
        self._preview.select_cells(selected, current)
        self._status_label.setText("已恢复")

    def _restore_template_dict(self, d: dict):
        """从字典快照恢复整个模板（用于行列等结构变更的撤销/恢复）。"""
        self._template = TemplateModel.from_dict(d)
        self._preview.set_template(self._template)
        self._style_panel._template = self._template

    # ==================================================================
    # 复制 / 粘贴 / 格式拷贝 / 格式粘贴
    # ==================================================================
    def _copy(self):
        """复制选中单元格的文本和格式到内部剪贴板（按选区最小包围盒）。"""
        cells = self._preview.get_selected_cells_raw()
        if not cells:
            self._status_label.setText("未选中任何单元格")
            return
        min_r = min(r for r, _ in cells)
        min_c = min(c for _, c in cells)
        max_r = max(r for r, _ in cells)
        max_c = max(c for _, c in cells)
        cb_cells = {}
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                cd = self._template.get_cell_data(r, c)
                text = cd.static_text if cd.static_text else ""
                style = self._template.get_effective_style(r, c).clone()
                cb_cells[(r - min_r, c - min_c)] = (text, style)
        self._clipboard = {
            "height": max_r - min_r + 1,
            "width": max_c - min_c + 1,
            "cells": cb_cells,
            "merges": [
                (mr.top_row - min_r, mr.bottom_row - min_r,
                 mr.left_col - min_c, mr.right_col - min_c)
                for mr in self._template.merge_ranges
                if (mr.top_row >= min_r and mr.bottom_row <= max_r and
                    mr.left_col >= min_c and mr.right_col <= max_c)
            ],
        }
        rows = []
        for dr in range(self._clipboard["height"]):
            rows.append("\t".join(cb_cells[(dr, dc)][0]
                                  for dc in range(self._clipboard["width"])))
        self._clipboard_system_text = "\n".join(rows)
        QApplication.clipboard().setText(self._clipboard_system_text)
        self._preview.clear_paste_anchor()
        self._status_label.setText(f"已复制 {len(cb_cells)} 个单元格")

    def _copy_format(self):
        """格式拷贝：只复制选中单元格的格式到格式剪贴板（不复制文本）。"""
        cells = self._preview.get_selected_cells_raw()
        if not cells:
            self._status_label.setText("未选中任何单元格")
            return
        min_r = min(r for r, _ in cells)
        min_c = min(c for _, c in cells)
        max_r = max(r for r, _ in cells)
        max_c = max(c for _, c in cells)
        cb_cells = {}
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                cb_cells[(r - min_r, c - min_c)] = self._template.get_effective_style(r, c).clone()
        self._format_clipboard = {
            "height": max_r - min_r + 1,
            "width": max_c - min_c + 1,
            "cells": cb_cells,
            "merges": [
                (mr.top_row - min_r, mr.bottom_row - min_r,
                 mr.left_col - min_c, mr.right_col - min_c)
                for mr in self._template.merge_ranges
                if (mr.top_row >= min_r and mr.bottom_row <= max_r and
                    mr.left_col >= min_c and mr.right_col <= max_c)
            ],
        }
        self._status_label.setText(f"已拷贝格式（{len(cb_cells)} 个单元格）")

    def _paste_anchor(self):
        """确定粘贴起始位置；单格选择时优先使用刚点击的当前格。"""
        clicked = self._preview.paste_anchor_cell()
        if clicked is not None:
            return clicked
        cells = self._preview.get_selected_cells()
        if len(cells) <= 1:
            row, col = self._preview.currentRow(), self._preview.currentColumn()
            if row >= 0 and col >= 0:
                mr = self._template.get_merge_range(row, col)
                return (mr.top_row, mr.left_col) if mr else (row, col)
        if cells:
            return min(r for r, _ in cells), min(c for _, c in cells)
        scope, row, col = self._preview.get_current_scope_info()
        if row >= 0 and col >= 0:
            return row, col
        return 0, 0

    @staticmethod
    def _clipboard_from_text(text: str) -> dict | None:
        """把 Excel/WPS 系统剪贴板的 TSV 文本转换为二维剪贴板。"""
        if not text:
            return None
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not lines:
            return None
        matrix = [line.split("\t") for line in lines]
        width = max(len(row) for row in matrix)
        cells = {}
        for r, row in enumerate(matrix):
            for c in range(width):
                cells[(r, c)] = (row[c] if c < len(row) else "", None)
        return {"height": len(matrix), "width": width, "cells": cells, "merges": []}

    def _active_clipboard(self) -> dict | None:
        system_text = QApplication.clipboard().text()
        if system_text and system_text != self._clipboard_system_text:
            return self._clipboard_from_text(system_text)
        return self._clipboard

    def _paste_mapping(self, clipboard: dict) -> list[tuple[int, int, int, int]] | None:
        """返回 (目标行,目标列,源相对行,源相对列)，遵循 Excel 矩形粘贴规则。"""
        selected = self._preview.get_selected_cells()
        source_h, source_w = clipboard["height"], clipboard["width"]
        clicked = self._preview.paste_anchor_cell()
        if clicked is not None:
            start_r, start_c = clicked
            return [(start_r + dr, start_c + dc, dr, dc)
                    for dr in range(source_h) for dc in range(source_w)
                    if start_r + dr < self._template.rows and start_c + dc < self._template.cols]
        if len(selected) <= 1:
            start_r, start_c = self._paste_anchor()
            return [(start_r + dr, start_c + dc, dr, dc)
                    for dr in range(source_h) for dc in range(source_w)
                    if start_r + dr < self._template.rows and start_c + dc < self._template.cols]

        selected_set = set(selected)
        min_r = min(r for r, _ in selected); max_r = max(r for r, _ in selected)
        min_c = min(c for _, c in selected); max_c = max(c for _, c in selected)
        target_h, target_w = max_r - min_r + 1, max_c - min_c + 1
        if source_h != 1 or source_w != 1:
            if target_h % source_h or target_w % source_w:
                return None
        return [(r, c, (r - min_r) % source_h, (c - min_c) % source_w)
                for r, c in sorted(selected_set)]

    def _paste_from_clipboard(self, clipboard: dict, paste_text: bool, paste_style: bool):
        mapping = self._paste_mapping(clipboard)
        if mapping is None:
            QMessageBox.warning(self, "无法粘贴",
                                "复制区域与粘贴区域的大小不同，且目标区域不是源区域的整数倍。")
            return
        changes, affected = [], []
        old_merges = set(self._template.merge_ranges)
        for tr, tc, sr, sc in mapping:
            if tr >= self._template.rows or tc >= self._template.cols:
                continue
            text, style = clipboard["cells"][(sr, sc)]
            if paste_text:
                cd = self._template.get_cell_data(tr, tc)
                old_text = cd.static_text or ""
                if old_text != text:
                    changes.append(("text", tr, tc, old_text, text))
                    cd.static_text = text
                    self._template.set_cell_data(tr, tc, cd)
            if paste_style and style is not None:
                old_style = self._template.cell_styles.get((tr, tc))
                old_copy = old_style.clone() if old_style else None
                new_style = style.clone()
                if old_copy != new_style:
                    changes.append(("style", tr, tc, old_copy, new_style))
                    self._template.set_cell_style(tr, tc, new_style)
            affected.append((tr, tc))
        if paste_style and clipboard.get("merges") and affected:
            min_r = min(r for r, _ in affected); min_c = min(c for _, c in affected)
            source_h, source_w = clipboard["height"], clipboard["width"]
            target_h = max(r for r, _ in affected) - min_r + 1
            target_w = max(c for _, c in affected) - min_c + 1
            for tile_r in range(0, target_h, source_h):
                for tile_c in range(0, target_w, source_w):
                    for top, bottom, left, right in clipboard["merges"]:
                        t, b = min_r + tile_r + top, min_r + tile_r + bottom
                        l, rr = min_c + tile_c + left, min_c + tile_c + right
                        if b < self._template.rows and rr < self._template.cols:
                            self._template.add_merge_range(t, b, l, rr)
            if old_merges != self._template.merge_ranges:
                changes.append(("merges", old_merges, set(self._template.merge_ranges)))
        self._undo_mgr.record_batch(changes)
        self._preview.refresh_all()
        self._preview.select_cells(affected, affected[0] if affected else None)
        self._status_label.setText(f"已粘贴到 {len(affected)} 个单元格")

    def _paste(self):
        """粘贴剪贴板内容（文本 + 格式）到当前选区。"""
        clipboard = self._active_clipboard()
        if not clipboard:
            self._status_label.setText("剪贴板为空")
            return
        self._paste_from_clipboard(clipboard, paste_text=True, paste_style=True)

    def _paste_values(self):
        """仅粘贴内容，支持来自 Excel/WPS 的 TSV 数据。"""
        clipboard = self._active_clipboard()
        if not clipboard:
            self._status_label.setText("剪贴板为空")
            return
        self._paste_from_clipboard(clipboard, paste_text=True, paste_style=False)

    def _paste_format(self):
        """格式粘贴：只粘贴格式剪贴板中的格式，不改变文本。"""
        if not self._format_clipboard:
            self._status_label.setText("格式剪贴板为空，请先格式拷贝")
            return
        clipboard = {
            "height": self._format_clipboard["height"],
            "width": self._format_clipboard["width"],
            "cells": {pos: ("", style) for pos, style in self._format_clipboard["cells"].items()},
            "merges": self._format_clipboard.get("merges", []),
        }
        self._paste_from_clipboard(clipboard, paste_text=False, paste_style=True)

    # ==================================================================
    # 文件操作
    # ==================================================================
    def _new_template(self):
        """新建空白模板。"""
        rows, ok = QInputDialog.getInt(self, "新建模板", "输入行数:", 30, 1, 200)
        if not ok:
            return
        cols, ok = QInputDialog.getInt(self, "新建模板", "输入列数:", 10, 1, 50)
        if not ok:
            return
        self._template = TemplateModel(rows=rows, cols=cols)
        self._undo_mgr.clear()
        self._preview.set_template(self._template)
        self._style_panel._template = self._template
        self._current_filepath = ""
        self._status_label.setText(f"新建模板: {rows} 行 x {cols} 列")

    def _rebuild_preset_menu(self):
        """重建预设模板菜单（内置 + 自定义）。"""
        from templates.presets import BUILTIN_TEMPLATES, get_custom_presets, load_template_by_name
        self._preset_menu.clear()

        # 分隔线前的内置模板
        for name in BUILTIN_TEMPLATES:
            action = QAction(f"[内置] {name}", self)
            action.triggered.connect(lambda checked, n=name: self._load_preset_by_name(n))
            self._preset_menu.addAction(action)

        # 自定义模板
        custom = get_custom_presets()
        if custom:
            self._preset_menu.addSeparator()
            for name in custom:
                action = QAction(f"[自定义] {name}", self)
                action.triggered.connect(lambda checked, n=name: self._load_preset_by_name(n))
                self._preset_menu.addAction(action)

    def _load_preset(self, preset_func):
        """加载内置预设模板。"""
        template = preset_func()
        self._apply_loaded_template(template, "预设模板")

    def _load_preset_by_name(self, name: str):
        """根据名称加载模板（内置或自定义）。"""
        from templates.presets import load_template_by_name
        try:
            template = load_template_by_name(name)
            self._apply_loaded_template(template, name)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载模板 '{name}':\n{e}")

    def _save_as_preset(self):
        """将当前模板保存为自定义预设。"""
        from templates.presets import save_as_custom_preset
        name, ok = QInputDialog.getText(self, "保存为预设", "请输入预设模板名称:")
        if not ok or not name.strip():
            return
        try:
            save_as_custom_preset(self._template, name.strip())
            self._rebuild_preset_menu()
            self._status_label.setText(f"已保存预设: {name.strip()}")
            QMessageBox.information(self, "保存成功", f"模板已保存为预设 '{name.strip()}'")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存预设:\n{e}")

    def _import_preset(self):
        """从外部 JSON 文件导入为自定义预设。"""
        from templates.presets import import_custom_preset
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入预设模板",
            self._last_directory,
            "JSON 文件 (*.json)",
        )
        if not filepath:
            return
        try:
            name = import_custom_preset(filepath)
            self._rebuild_preset_menu()
            self._status_label.setText(f"已导入预设: {name}")
            QMessageBox.information(self, "导入成功", f"已导入预设模板 '{name}'")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法导入预设:\n{e}")

    def _delete_preset(self):
        """删除一个自定义预设。"""
        from templates.presets import get_custom_presets, delete_custom_preset
        custom = get_custom_presets()
        if not custom:
            QMessageBox.information(self, "提示", "没有自定义预设可删除")
            return
        names = list(custom.keys())
        name, ok = QInputDialog.getItem(self, "删除预设", "选择要删除的预设模板:", names, 0, False)
        if not ok:
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除预设 '{name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_custom_preset(name)
            self._rebuild_preset_menu()
            self._status_label.setText(f"已删除预设: {name}")

    def _load_template(self):
        """从 JSON 文件加载模板。"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开模板文件",
            self._last_directory,
            "模板文件 (*.json)",
        )
        if not filepath:
            return
        self._last_directory = os.path.dirname(filepath)
        self._settings.setValue("last_directory", self._last_directory)
        try:
            template = TemplateIO.load(filepath)
            self._apply_loaded_template(template, os.path.basename(filepath))
            self._current_filepath = filepath
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载模板:\n{e}")

    def _save_template(self):
        """保存当前模板。"""
        if not self._current_filepath:
            return self._save_as_template()
        try:
            TemplateIO.save(self._template, self._current_filepath)
            self._status_label.setText(f"已保存: {self._current_filepath}")
            QMessageBox.information(self, "保存成功", f"模板已保存到:\n{self._current_filepath}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存:\n{e}")

    def _save_as_template(self):
        """另存为 JSON 文件。"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "另存模板",
            os.path.join(self._last_directory, "报表模板.json"),
            "模板文件 (*.json)",
        )
        if not filepath:
            return
        self._last_directory = os.path.dirname(filepath)
        self._settings.setValue("last_directory", self._last_directory)
        try:
            TemplateIO.save_as(self._template, filepath)
            self._current_filepath = filepath
            self._status_label.setText(f"已保存: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存:\n{e}")

    def _apply_loaded_template(self, template: TemplateModel, name: str):
        """应用加载的模板到界面（更新引用，不重建 widget）。"""
        self._undo_mgr.clear()
        self._template = template
        self._template.template_name = name
        self._preview.set_template(self._template)
        self._style_panel._template = self._template
        self._status_label.setText(f"已加载: {name}")
        self._refresh_query_results()

    # ==================================================================
    # 导入导出
    # ==================================================================
    def _import_excel(self):
        """从 Excel 导入首个工作表的内容、布局和样式。"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入 Excel 文件",
            self._last_directory,
            "Excel 工作簿 (*.xlsx *.xlsm);;旧版 Excel (*.xls)",
        )
        if not filepath:
            return

        try:
            template = ExcelImporter.import_file(filepath)
            self._last_directory = os.path.dirname(filepath)
            self._settings.setValue("last_directory", self._last_directory)
            self._apply_loaded_template(template, template.template_name)
            self._current_filepath = ""
            self._status_label.setText(f"已完整导入 Excel: {filepath}")
        except Exception as e:
            err_msg = str(e)
            if filepath.lower().endswith(".xls") or "not a zip" in err_msg.lower() or "zipfile" in err_msg.lower():
                QMessageBox.warning(
                    self, "格式不支持",
                    "该文件不是有效的 .xlsx 格式。\n\n"
                    "如果是 .xls 旧格式文件，请先用 Excel 打开，\n"
                    "通过 文件→另存为 选择 .xlsx 格式保存后再导入。"
                )
            else:
                QMessageBox.critical(self, "导入失败", f"无法导入 Excel:\n{err_msg}")

    def _export_excel(self):
        """导出到 Excel 文件。"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel 文件",
            os.path.join(self._last_directory, "生产运行日报.xlsx"),
            "Excel 文件 (*.xlsx)",
        )
        if not filepath:
            return

        try:
            # 若存在查询绑定，确保数据库已连接
            if not self._db_handler.is_connected("default"):
                config = self._template.db_configs.get("default")
                if config:
                    self._db_handler.connect(config, "default")

            # 准备数据（优先使用 cell_data 中的 static_text）
            data = self._preview.get_data()

            # 数据库查询回调
            def query_callback(row: int, col: int) -> str | None:
                cd = self._template.get_cell_data(row, col)
                qb = cd.query_binding
                if not qb or not qb.enabled:
                    return None
                sql = qb.build_sql(str(self._session.selected_date or date.today()))
                if not sql:
                    return None
                result = self._db_handler.execute_query(sql, qb.db_config_key or "default")
                return result

            ExcelExporter.export(self._template, data, filepath, query_callback)
            QMessageBox.information(self, "导出成功",
                                    f"Excel 已成功导出到:\n{filepath}")
            self._status_label.setText(f"已导出: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出时发生错误:\n{e}")

    # ==================================================================
    # 行列操作
    # ==================================================================
    def _merge_cells(self):
        """合并选中的单元格区域。"""
        cells = self._preview.get_selected_cells()
        if len(cells) < 2:
            QMessageBox.information(self, "提示", "请选择至少两个单元格进行合并")
            return

        rows = [c[0] for c in cells]
        cols = [c[1] for c in cells]
        old_merges = set(self._template.merge_ranges)
        self._template.add_merge_range(min(rows), max(rows), min(cols), max(cols))
        new_merges = set(self._template.merge_ranges)
        if old_merges != new_merges:
            self._undo_mgr.record_batch([("merges", old_merges, new_merges)])
        self._preview.refresh_all()
        self._status_label.setText(f"已合并单元格: {min(rows)+1}:{max(rows)+1}, {chr(65+min(cols))}:{chr(65+max(cols))}")

    def _unmerge_cells(self):
        """取消选中单元格所在的合并区域。"""
        cells = self._preview.get_selected_cells()
        if not cells:
            return
        old_merges = set(self._template.merge_ranges)
        for row, col in cells:
            self._template.remove_merge_range(row, col)
        new_merges = set(self._template.merge_ranges)
        if old_merges != new_merges:
            self._undo_mgr.record_batch([("merges", old_merges, new_merges)])
        self._preview.refresh_all()
        self._status_label.setText("已取消合并")

    def _insert_row(self):
        cells = self._preview.get_selected_cells()
        target = cells[0][0] if cells else 0
        old_dict = self._template.to_dict()
        self._template.insert_row(target)
        self._preview.sync_grid()
        self._undo_mgr.record_batch([("structure", old_dict, self._template.to_dict())])
        self._status_label.setText(f"已在第 {target + 1} 行前插入一行")

    def _delete_row(self):
        cells = self._preview.get_selected_cells()
        target = cells[0][0] if cells else 0
        old_dict = self._template.to_dict()
        self._template.delete_row(target)
        self._preview.sync_grid()
        self._undo_mgr.record_batch([("structure", old_dict, self._template.to_dict())])
        self._status_label.setText(f"已删除第 {target + 1} 行")

    def _insert_column(self):
        cells = self._preview.get_selected_cells()
        target = cells[0][1] if cells else 0
        old_dict = self._template.to_dict()
        self._template.insert_column(target)
        self._preview.sync_grid()
        self._undo_mgr.record_batch([("structure", old_dict, self._template.to_dict())])
        self._status_label.setText(f"已在列 {chr(65 + target)} 前插入一列")

    def _delete_column(self):
        cells = self._preview.get_selected_cells()
        target = cells[0][1] if cells else 0
        old_dict = self._template.to_dict()
        self._template.delete_column(target)
        self._preview.sync_grid()
        self._undo_mgr.record_batch([("structure", old_dict, self._template.to_dict())])
        self._status_label.setText(f"已删除列 {chr(65 + target)}")

    # ==================================================================
    # 数据库配置
    # ==================================================================
    def _get_db_metadata(self, config_key: str = "default") -> dict[str, list[str]]:
        """Connect when possible and expose tables/columns to the query builder."""
        if not self._db_handler.is_connected(config_key):
            config = self._template.db_configs.get(config_key)
            if not config or not self._db_handler.connect(config, config_key):
                return {}
        return self._db_handler.get_schema_metadata(config_key)

    def _db_config(self):
        """数据库连接配置。"""
        dlg = _DbConfigDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            config = dlg.get_config()
            self._template.db_configs["default"] = config
            self._status_label.setText("数据库配置已更新")

    def _db_test_connect(self):
        """测试数据库连接。"""
        config = self._template.db_configs.get("default")
        if not config:
            QMessageBox.warning(self, "提示", "请先在数据库菜单中配置连接信息")
            return
        success = self._db_handler.connect(config, "default")
        if success:
            QMessageBox.information(self, "连接成功", "数据库连接测试通过")
        else:
            QMessageBox.critical(self, "连接失败", "数据库连接测试失败，请检查配置")

    def _refresh_query_results(self):
        """执行所有数据库绑定单元格的查询，更新预览显示结果。"""
        if not self._db_handler.is_connected("default"):
            # 尝试用已保存配置自动连接
            config = self._template.db_configs.get("default")
            if config:
                self._db_handler.connect(config, "default")
        results = {}
        for (r, c), cd in self._template.cell_data.items():
            qb = cd.query_binding
            if not qb or not qb.enabled:
                continue
            sql = qb.build_sql(str(self._session.selected_date or date.today()))
            if not sql:
                continue
            val = self._db_handler.execute_query(sql, qb.db_config_key or "default")
            if val is not None:
                results[(r, c)] = val
        self._preview.set_query_results(results)
        self._status_label.setText(f"已刷新查询结果（{len(results)} 个单元格）")

    # ==================================================================
    # 重置模板
    # ==================================================================
    def _reset_template(self):
        """重置模板 —— 确认后清空所有配置，回到空白基础模板。"""
        reply = QMessageBox.warning(
            self,
            "确认重置模板",
            "此操作将清空所有自定义样式、合并布局、文字内容、\n"
            "数据库绑定及自定义行列尺寸。\n\n"
            "此操作仅作用于当前编辑页面，不会改动本地已存模板，\n"
            "且无法撤销。\n\n"
            "确认要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._template.clear_all()
            self._undo_mgr.clear()
            self._template.default_style = CellStyle(
                font_family="宋体", font_family_western="Times New Roman", font_size=10,
                alignment=int(Qt.AlignmentFlag.AlignCenter),
            )
            self._preview.set_template(self._template)
            self._style_panel._template = self._template
            self._status_label.setText("模板已重置为空白基础模板")

    # ==================================================================
    # 会话持久化
    # ==================================================================
    def _restore_last_session(self):
        """启动时尝试恢复上一次的编辑状态。"""
        # 优先加载上次会话文件
        if os.path.exists(_SESSION_FILE):
            try:
                template = TemplateIO.load(_SESSION_FILE)
                self._apply_loaded_template(template, "上次会话")
                self._status_label.setText("已恢复上次编辑状态")
                return
            except Exception:
                pass
        # 否则尝试加载默认模板
        if os.path.exists(_DEFAULT_TEMPLATE_FILE):
            try:
                template = TemplateIO.load(_DEFAULT_TEMPLATE_FILE)
                self._apply_loaded_template(template, "默认模板")
                self._status_label.setText("已加载默认模板")
            except Exception:
                pass

    def _save_session(self):
        """保存当前编辑状态到会话文件。"""
        try:
            TemplateIO.save(self._template, _SESSION_FILE)
        except Exception:
            pass

    def closeEvent(self, event):
        """窗口关闭时保存当前状态。"""
        # 保存模板会话
        self._save_session()
        # 保存窗口几何
        self._settings.setValue("window_geometry", self.saveGeometry())
        self._settings.setValue("last_directory", self._last_directory)
        event.accept()

    # ==================================================================
    # 默认模板设置
    # ==================================================================
    def _set_default_template(self):
        """选择一个 JSON 文件作为默认模板，备份到本地。"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择默认模板文件",
            self._last_directory,
            "模板文件 (*.json)",
        )
        if not filepath:
            return
        try:
            # 复制源文件作为默认模板 + 备份
            shutil.copy2(filepath, _DEFAULT_TEMPLATE_FILE)
            shutil.copy2(filepath, _DEFAULT_BACKUP_FILE)
            QMessageBox.information(
                self, "设置成功",
                f"默认模板已设置:\n{_DEFAULT_TEMPLATE_FILE}\n\n"
                f"备份已创建:\n{_DEFAULT_BACKUP_FILE}"
            )
            self._status_label.setText("默认模板已设置")
        except Exception as e:
            QMessageBox.critical(self, "设置失败", f"无法设置默认模板:\n{e}")

    def _restore_default_template(self):
        """从备份文件恢复默认模板。"""
        if not os.path.exists(_DEFAULT_BACKUP_FILE):
            QMessageBox.information(self, "提示", 
                                    "尚未设置默认模板，请先使用 '设置默认模板' 功能")
            return
        reply = QMessageBox.question(
            self, "恢复默认模板",
            "将从备份文件恢复默认模板，当前未保存的更改将丢失。\n确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                template = TemplateIO.load(_DEFAULT_BACKUP_FILE)
                self._apply_loaded_template(template, "默认模板(已恢复)")
                self._status_label.setText("已恢复默认模板")
            except Exception as e:
                QMessageBox.critical(self, "恢复失败", f"无法恢复默认模板:\n{e}")
