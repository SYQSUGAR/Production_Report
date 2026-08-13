"""样式配置面板（增强版）—— 三组可折叠配置区域。

第一组：字体、底色、对齐、边框、数字格式
第二组：数据库绑定开关与配置
第三组：合并范围查看、备注、行列尺寸
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QButtonGroup,
    QColorDialog, QFrame, QSizePolicy, QScrollArea, QToolBox,
    QTextEdit, QLineEdit, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase

from models.template_model import (
    TemplateModel, CellStyle, StyleScope, BorderStyle, NumberFormat, CellData,
)
from models.db_config import QueryBinding, QueryType


_SCOPE_MAP = {
    "当前单元格": StyleScope.CELL,
    "当前行": StyleScope.ROW,
    "当前列": StyleScope.COLUMN,
    "全局默认": StyleScope.DEFAULT,
}


class StylePanel(QScrollArea):
    """可滚动的样式配置面板，使用 QToolBox 实现三组折叠。"""

    style_changed = pyqtSignal()  # 通知外部刷新预览

    def __init__(self, template: TemplateModel, parent=None):
        super().__init__(parent)
        self._template = template
        self._current_scope = StyleScope.DEFAULT
        self._current_row = -1
        self._current_col = -1
        self._selected_cells: list[tuple[int, int]] = []  # 多选单元格列表

        self.setWidgetResizable(True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)

        self._suppress_update = False

        self._container = QWidget()
        self.setWidget(self._container)
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        # 当前选中范围
        self._build_selection_info()

        # 折叠面板
        self._toolbox = QToolBox()
        self._build_style_group()    # 字体/颜色/对齐/边框/数字格式
        self._build_db_group()       # 数据库绑定
        self._main_layout.addWidget(self._toolbox, 1)

        # 应用范围按钮
        self._build_apply_buttons()
        self._build_action_buttons()

    # ==================================================================
    # 选取信息
    # ==================================================================
    def _build_selection_info(self):
        grp = QGroupBox("当前选中范围")
        lay = QVBoxLayout(grp)
        self._lbl_scope = QLabel("全局默认")
        self._lbl_scope.setStyleSheet("font-weight:bold; color:#1A73E8; font-size:13px;")
        self._lbl_scope.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_scope.setWordWrap(True)
        lay.addWidget(self._lbl_scope)
        self._main_layout.addWidget(grp)

    # ==================================================================
    # 第一组：字体 / 颜色 / 对齐 / 边框 / 数字格式
    # ==================================================================
    def _build_style_group(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # --- 字体 ---
        font_grp = QGroupBox("字体")
        fl = QVBoxLayout(font_grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("中文:"))
        self._cmb_font = QComboBox()
        self._cmb_font.addItems(QFontDatabase.families())
        self._cmb_font.setCurrentText("宋体")
        self._cmb_font.currentTextChanged.connect(self._on_cjk_font_changed)
        r1.addWidget(self._cmb_font, 1)
        fl.addLayout(r1)

        r1w = QHBoxLayout()
        r1w.addWidget(QLabel("西文:"))
        self._cmb_font_western = QComboBox()
        self._cmb_font_western.addItems(QFontDatabase.families())
        self._cmb_font_western.setCurrentText("Times New Roman")
        self._cmb_font_western.currentTextChanged.connect(self._on_western_font_changed)
        r1w.addWidget(self._cmb_font_western, 1)
        fl.addLayout(r1w)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("字号:"))
        self._spn_size = QSpinBox()
        self._spn_size.setRange(6, 72)
        self._spn_size.setValue(10)
        self._spn_size.valueChanged.connect(self._on_size_changed)
        r2.addWidget(self._spn_size)
        r2.addStretch()
        fl.addLayout(r2)

        r3 = QHBoxLayout()
        self._chk_bold = QCheckBox("粗体")
        self._chk_bold.stateChanged.connect(self._on_bold_changed)
        self._chk_italic = QCheckBox("斜体")
        self._chk_italic.stateChanged.connect(self._on_italic_changed)
        self._chk_underline = QCheckBox("下划线")
        self._chk_underline.stateChanged.connect(self._on_underline_changed)
        r3.addWidget(self._chk_bold)
        r3.addWidget(self._chk_italic)
        r3.addWidget(self._chk_underline)
        fl.addLayout(r3)
        lay.addWidget(font_grp)

        # --- 对齐 ---
        align_grp = QGroupBox("水平对齐")
        al = QHBoxLayout(align_grp)
        self._btn_align_left = QPushButton("左")
        self._btn_align_center = QPushButton("中")
        self._btn_align_right = QPushButton("右")
        for btn in (self._btn_align_left, self._btn_align_center, self._btn_align_right):
            btn.setCheckable(True)
            btn.setFixedHeight(28)
        self._align_group = QButtonGroup(self)
        self._align_group.addButton(self._btn_align_left, 0)
        self._align_group.addButton(self._btn_align_center, 1)
        self._align_group.addButton(self._btn_align_right, 2)
        self._align_group.idClicked.connect(self._on_alignment_changed)
        al.addWidget(self._btn_align_left)
        al.addWidget(self._btn_align_center)
        al.addWidget(self._btn_align_right)
        lay.addWidget(align_grp)

        # --- 垂直对齐 ---
        valign_grp = QGroupBox("垂直对齐")
        vl = QHBoxLayout(valign_grp)
        self._btn_valign_top = QPushButton("上")
        self._btn_valign_center = QPushButton("中")
        self._btn_valign_bottom = QPushButton("下")
        for btn in (self._btn_valign_top, self._btn_valign_center, self._btn_valign_bottom):
            btn.setCheckable(True)
            btn.setFixedHeight(28)
        self._valign_group = QButtonGroup(self)
        self._valign_group.addButton(self._btn_valign_top, 0)
        self._valign_group.addButton(self._btn_valign_center, 1)
        self._valign_group.addButton(self._btn_valign_bottom, 2)
        self._valign_group.idClicked.connect(self._on_valignment_changed)
        vl.addWidget(self._btn_valign_top)
        vl.addWidget(self._btn_valign_center)
        vl.addWidget(self._btn_valign_bottom)
        lay.addWidget(valign_grp)

        # --- 颜色 ---
        color_grp = QGroupBox("颜色")
        cl = QVBoxLayout(color_grp)
        cr1 = QHBoxLayout()
        cr1.addWidget(QLabel("字体色:"))
        self._btn_fg_color = QPushButton()
        self._btn_fg_color.setFixedSize(28, 28)
        self._btn_fg_color.setStyleSheet("background-color:#000000; border:1px solid #999; border-radius:3px;")
        self._btn_fg_color.clicked.connect(self._on_fg_color_clicked)
        self._chk_fg_reset = QCheckBox("默认")
        self._chk_fg_reset.setChecked(True)
        self._chk_fg_reset.stateChanged.connect(self._on_fg_reset_changed)
        cr1.addWidget(self._btn_fg_color)
        cr1.addWidget(self._chk_fg_reset)
        cr1.addStretch()
        cl.addLayout(cr1)

        cr2 = QHBoxLayout()
        cr2.addWidget(QLabel("背景色:"))
        self._btn_bg_color = QPushButton()
        self._btn_bg_color.setFixedSize(28, 28)
        self._btn_bg_color.setStyleSheet("background-color:#FFFFFF; border:1px solid #999; border-radius:3px;")
        self._btn_bg_color.clicked.connect(self._on_bg_color_clicked)
        self._chk_bg_reset = QCheckBox("默认")
        self._chk_bg_reset.setChecked(True)
        self._chk_bg_reset.stateChanged.connect(self._on_bg_reset_changed)
        cr2.addWidget(self._btn_bg_color)
        cr2.addWidget(self._chk_bg_reset)
        cr2.addStretch()
        cl.addLayout(cr2)
        lay.addWidget(color_grp)

        # --- 边框 ---
        border_grp = QGroupBox("边框")
        bl = QVBoxLayout(border_grp)

        # 线型
        br_style = QHBoxLayout()
        br_style.addWidget(QLabel("线型:"))
        self._cmb_border_style = QComboBox()
        self._cmb_border_style.addItems(["实线", "虚线", "点线", "点划线", "双线", "无"])
        self._cmb_border_style.setCurrentIndex(0)
        self._cmb_border_style.currentIndexChanged.connect(self._on_border_style_changed)
        br_style.addWidget(self._cmb_border_style, 1)
        bl.addLayout(br_style)

        # 粗细
        br_weight = QHBoxLayout()
        br_weight.addWidget(QLabel("粗细:"))
        self._spn_border_width = QDoubleSpinBox()
        self._spn_border_width.setRange(0.5, 5.0)
        self._spn_border_width.setSingleStep(0.5)
        self._spn_border_width.setDecimals(1)
        self._spn_border_width.setValue(1.0)
        self._spn_border_width.setSuffix(" px")
        self._spn_border_width.valueChanged.connect(self._on_border_width_changed)
        br_weight.addWidget(self._spn_border_width)
        br_weight.addStretch()
        bl.addLayout(br_weight)

        # 方向
        br_dir = QHBoxLayout()
        self._chk_border_top = QCheckBox("上")
        self._chk_border_bottom = QCheckBox("下")
        self._chk_border_left = QCheckBox("左")
        self._chk_border_right = QCheckBox("右")
        self._chk_border_top.stateChanged.connect(lambda *_: self._on_border_dir_changed("top"))
        self._chk_border_bottom.stateChanged.connect(lambda *_: self._on_border_dir_changed("bottom"))
        self._chk_border_left.stateChanged.connect(lambda *_: self._on_border_dir_changed("left"))
        self._chk_border_right.stateChanged.connect(lambda *_: self._on_border_dir_changed("right"))
        for chk in (self._chk_border_top, self._chk_border_bottom,
                    self._chk_border_left, self._chk_border_right):
            br_dir.addWidget(chk)
        bl.addLayout(br_dir)

        # 预览
        self._lbl_border_preview = QLabel("边框预览")
        self._lbl_border_preview.setFixedHeight(36)
        self._lbl_border_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_border_preview.setStyleSheet(
            "border:2px solid #D5D9E0; border-radius:4px; background:#FAFBFC; color:#A0A8B4;"
        )
        bl.addWidget(self._lbl_border_preview)
        lay.addWidget(border_grp)

        # --- 数字格式（两级设置，类 Excel）---
        nf_grp = QGroupBox("数字格式")
        nf_lay = QVBoxLayout(nf_grp)
        # 第一级：类别
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("类别:"))
        self._cmb_number_cat = QComboBox()
        self._cmb_number_cat.addItems(["常规", "数值", "日期", "百分比", "文本", "自定义"])
        self._cmb_number_cat.setCurrentIndex(0)
        self._cmb_number_cat.currentIndexChanged.connect(self._on_number_cat_changed)
        cat_row.addWidget(self._cmb_number_cat, 1)
        nf_lay.addLayout(cat_row)

        # 第二级：子选项容器（动态切换）
        self._nf_sub_widget = QWidget()
        self._nf_sub_layout = QVBoxLayout(self._nf_sub_widget)
        self._nf_sub_layout.setContentsMargins(0, 2, 0, 0)
        self._nf_sub_layout.setSpacing(4)

        # -- 数值/百分比：小数位数 --
        dec_row = QHBoxLayout()
        dec_row.addWidget(QLabel("小数位数:"))
        self._spn_nf_decimals = QSpinBox()
        self._spn_nf_decimals.setRange(0, 10)
        self._spn_nf_decimals.setValue(2)
        self._spn_nf_decimals.valueChanged.connect(self._on_number_format_changed)
        dec_row.addWidget(self._spn_nf_decimals)
        dec_row.addStretch()
        self._nf_decimals_row = QWidget()
        self._nf_decimals_row.setLayout(dec_row)

        # -- 日期：格式选项 --
        self._cmb_nf_date = QComboBox()
        self._cmb_nf_date.addItems([
            "yyyy-mm-dd", "yyyy/mm/dd", "yyyy年mm月dd日",
            "mm-dd", "mm/dd", "yyyy-mm", "yyyy/mm",
        ])
        self._cmb_nf_date.currentIndexChanged.connect(self._on_number_format_changed)

        # -- 自定义：自由输入 --
        self._txt_nf_custom = QLineEdit()
        self._txt_nf_custom.setPlaceholderText("输入自定义格式，如 0.0000、¥#,##0.00")
        self._txt_nf_custom.textChanged.connect(self._on_number_format_changed)

        # -- 常规/文本：提示文字 --
        self._lbl_nf_hint = QLabel("无任何特定数字格式")
        self._lbl_nf_hint.setStyleSheet("color:#888; font-size:11px;")

        self._nf_sub_layout.addWidget(self._nf_decimals_row)
        self._nf_sub_layout.addWidget(self._cmb_nf_date)
        self._nf_sub_layout.addWidget(self._txt_nf_custom)
        self._nf_sub_layout.addWidget(self._lbl_nf_hint)
        nf_lay.addWidget(self._nf_sub_widget)

        # 默认：常规 → 显示提示
        self._on_number_cat_changed(0)

        lay.addWidget(nf_grp)

        lay.addStretch()
        self._toolbox.addItem(page, "📐  字体 / 样式 / 边框")

    # ==================================================================
    # 第二组：数据库绑定
    # ==================================================================
    def _build_db_group(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # 绑定开关
        self._chk_db_enabled = QCheckBox("启用数据库绑定")
        self._chk_db_enabled.stateChanged.connect(self._on_db_enabled_changed)
        lay.addWidget(self._chk_db_enabled)

        # 查询类型
        qt_row = QHBoxLayout()
        qt_row.addWidget(QLabel("查询类型:"))
        self._cmb_query_type = QComboBox()
        self._cmb_query_type.addItems(["单值查询", "聚合查询"])
        self._cmb_query_type.currentIndexChanged.connect(self._on_db_config_changed)
        qt_row.addWidget(self._cmb_query_type, 1)
        lay.addLayout(qt_row)

        # 聚合函数
        agg_row = QHBoxLayout()
        agg_row.addWidget(QLabel("聚合:"))
        self._cmb_aggregate = QComboBox()
        self._cmb_aggregate.addItems(["SUM", "COUNT", "AVG", "MAX", "MIN"])
        self._cmb_aggregate.currentIndexChanged.connect(self._on_db_config_changed)
        agg_row.addWidget(self._cmb_aggregate, 1)
        lay.addLayout(agg_row)

        # 数据表
        tbl_row = QHBoxLayout()
        tbl_row.addWidget(QLabel("数据表:"))
        self._txt_table = QLineEdit()
        self._txt_table.setPlaceholderText("如: daily_production")
        self._txt_table.textChanged.connect(self._on_db_config_changed)
        tbl_row.addWidget(self._txt_table, 1)
        lay.addLayout(tbl_row)

        # 字段
        fld_row = QHBoxLayout()
        fld_row.addWidget(QLabel("字段:"))
        self._txt_field = QLineEdit()
        self._txt_field.setPlaceholderText("如: output_volume")
        self._txt_field.textChanged.connect(self._on_db_config_changed)
        fld_row.addWidget(self._txt_field, 1)
        lay.addLayout(fld_row)

        # 日期占位符
        dp_row = QHBoxLayout()
        dp_row.addWidget(QLabel("日期占位符:"))
        self._txt_date_ph = QLineEdit()
        self._txt_date_ph.setPlaceholderText("如: {date}")
        self._txt_date_ph.textChanged.connect(self._on_db_config_changed)
        dp_row.addWidget(self._txt_date_ph, 1)
        lay.addLayout(dp_row)

        # 筛选条件
        lay.addWidget(QLabel("筛选条件 (每行一个, 格式: 字段 运算符 值):"))
        self._txt_filters = QTextEdit()
        self._txt_filters.setFixedHeight(80)
        self._txt_filters.setPlaceholderText("例如:\ndate = {date}\nstation_id = 001")
        self._txt_filters.textChanged.connect(self._on_db_config_changed)
        lay.addWidget(self._txt_filters)

        # 预览 SQL
        lay.addWidget(QLabel("预览 SQL:"))
        self._lbl_sql_preview = QLabel("-")
        self._lbl_sql_preview.setWordWrap(True)
        self._lbl_sql_preview.setStyleSheet("background:#F8F9FC; padding:4px; border-radius:3px; border:1px solid #E0E3E8;")
        lay.addWidget(self._lbl_sql_preview)

        lay.addStretch()
        self._toolbox.addItem(page, "🗄️  数据库绑定")

    # ==================================================================
    # 应用范围按钮
    # ==================================================================
    def _build_apply_buttons(self):
        grp = QGroupBox("应用样式到")
        lay = QHBoxLayout(grp)
        lay.setSpacing(4)

        btn_cell = QPushButton("单元格")
        btn_row = QPushButton("本行")
        btn_col = QPushButton("本列")
        btn_default = QPushButton("全局")

        for btn in (btn_cell, btn_row, btn_col, btn_default):
            btn.setFixedHeight(30)
            btn.clicked.connect(self._on_apply_clicked)
            lay.addWidget(btn)

        self._main_layout.addWidget(grp)

    # ==================================================================
    # 操作按钮
    # ==================================================================
    def _build_action_buttons(self):
        lay = QHBoxLayout()
        lay.setSpacing(4)

        btn_reset = QPushButton("清除当前范围")
        btn_reset.setFixedHeight(30)
        btn_reset.setStyleSheet("color:#D93025; border:1px solid #F5C6CB;")
        btn_reset.clicked.connect(self._on_reset_clicked)
        lay.addWidget(btn_reset)

        btn_clear_all = QPushButton("清除全部")
        btn_clear_all.setFixedHeight(30)
        btn_clear_all.setStyleSheet("color:#D93025; border:1px solid #F5C6CB;")
        btn_clear_all.clicked.connect(self._on_clear_all_clicked)
        lay.addWidget(btn_clear_all)

        self._main_layout.addLayout(lay)

    # ==================================================================
    # 更新当前选中范围
    # ==================================================================
    def set_selected_cells(self, cells: list):
        """记录当前多选的单元格列表。"""
        self._selected_cells = cells

    def set_current_selection(self, scope: str, row: int, col: int):
        self._current_scope = {
            "cell": StyleScope.CELL,
            "row": StyleScope.ROW,
            "column": StyleScope.COLUMN,
            "default": StyleScope.DEFAULT,
        }.get(scope, StyleScope.DEFAULT)
        self._current_row = row
        self._current_col = col

        # 多选时显示区域信息
        if len(self._selected_cells) > 1:
            rows = [c[0] for c in self._selected_cells]
            cols = [c[1] for c in self._selected_cells]
            self._lbl_scope.setText(
                f"选中区域: {chr(65 + min(cols))}{min(rows) + 1}:{chr(65 + max(cols))}{max(rows) + 1}"
                f" ({len(self._selected_cells)} 个单元格)"
            )
        else:
            desc_map = {
                StyleScope.CELL: f"单元格 ({row + 1}, {chr(65 + col)})" if row >= 0 and col >= 0 else "单元格",
                StyleScope.ROW: f"第 {row + 1} 行" if row >= 0 else "行",
                StyleScope.COLUMN: f"列 {chr(65 + col)}" if col >= 0 else "列",
                StyleScope.DEFAULT: "全局默认",
            }
            self._lbl_scope.setText(desc_map.get(self._current_scope, "—"))

        self._load_style_for_current_scope()
        self._load_db_binding()

    def _load_style_for_current_scope(self):
        """读取当前范围的样式到第一组面板。"""
        self._suppress_update = True

        style = self._get_current_style()
        if style is None:
            style = CellStyle()

        # 字体
        if style.font_family:
            idx = self._cmb_font.findText(style.font_family)
            if idx >= 0:
                self._cmb_font.setCurrentIndex(idx)
        else:
            self._cmb_font.setCurrentText("宋体")

        if style.font_family_western:
            idx_w = self._cmb_font_western.findText(style.font_family_western)
            if idx_w >= 0:
                self._cmb_font_western.setCurrentIndex(idx_w)
        else:
            self._cmb_font_western.setCurrentText("Times New Roman")

        self._spn_size.setValue(style.font_size if style.font_size else 10)

        self._chk_bold.setCheckState(
            Qt.CheckState.Checked if style.bold else
            Qt.CheckState.Unchecked if style.bold is False else
            Qt.CheckState.PartiallyChecked
        )
        self._chk_italic.setCheckState(
            Qt.CheckState.Checked if style.italic else
            Qt.CheckState.Unchecked if style.italic is False else
            Qt.CheckState.PartiallyChecked
        )
        self._chk_underline.setCheckState(
            Qt.CheckState.Checked if style.underline else
            Qt.CheckState.Unchecked if style.underline is False else
            Qt.CheckState.PartiallyChecked
        )

        # 对齐
        self._align_group.setExclusive(False)
        for btn in self._align_group.buttons():
            btn.setChecked(False)
        self._align_group.setExclusive(True)
        if style.alignment is not None:
            if style.alignment == int(Qt.AlignmentFlag.AlignLeft):
                self._btn_align_left.setChecked(True)
            elif style.alignment == int(Qt.AlignmentFlag.AlignCenter):
                self._btn_align_center.setChecked(True)
            elif style.alignment == int(Qt.AlignmentFlag.AlignRight):
                self._btn_align_right.setChecked(True)

        # 垂直对齐
        self._valign_group.setExclusive(False)
        for btn in self._valign_group.buttons():
            btn.setChecked(False)
        self._valign_group.setExclusive(True)
        if style.vertical_alignment is not None:
            if style.vertical_alignment == int(Qt.AlignmentFlag.AlignTop):
                self._btn_valign_top.setChecked(True)
            elif style.vertical_alignment == int(Qt.AlignmentFlag.AlignVCenter):
                self._btn_valign_center.setChecked(True)
            elif style.vertical_alignment == int(Qt.AlignmentFlag.AlignBottom):
                self._btn_valign_bottom.setChecked(True)

        # 颜色
        if style.fg_color:
            self._btn_fg_color.setStyleSheet(
                f"background-color:{style.fg_color}; border:1px solid #999; border-radius:3px;"
            )
            self._chk_fg_reset.setChecked(False)
        else:
            self._btn_fg_color.setStyleSheet(
                "background-color:#000000; border:1px solid #999; border-radius:3px;"
            )
            self._chk_fg_reset.setChecked(True)

        if style.bg_color:
            self._btn_bg_color.setStyleSheet(
                f"background-color:{style.bg_color}; border:1px solid #999; border-radius:3px;"
            )
            self._chk_bg_reset.setChecked(False)
        else:
            self._btn_bg_color.setStyleSheet(
                "background-color:#FFFFFF; border:1px solid #999; border-radius:3px;"
            )
            self._chk_bg_reset.setChecked(True)

        # 边框线型
        border_style_map = {
            "solid": 0, "dashed": 1, "dotted": 2, "dash_dot": 3, "double": 4, "none": 5,
            "thin": 0, "medium": 0, "thick": 0,  # 兼容旧格式
        }
        if style.border_line_style:
            self._cmb_border_style.setCurrentIndex(border_style_map.get(style.border_line_style, 0))

        self._spn_border_width.setValue(style.border_width if style.border_width else 1)

        # 边框方向
        self._chk_border_top.setChecked(bool(style.border_top))
        self._chk_border_bottom.setChecked(bool(style.border_bottom))
        self._chk_border_left.setChecked(bool(style.border_left))
        self._chk_border_right.setChecked(bool(style.border_right))

        # 更新边框预览
        self._update_border_preview()

        # 数字格式（两级设置：反向解析 → 设置类别和子选项）
        if style.number_format:
            nf = style.number_format
            if nf == "general":
                self._cmb_number_cat.setCurrentIndex(0)  # 常规
            elif nf == "integer":
                self._cmb_number_cat.setCurrentIndex(1)  # 数值
                self._spn_nf_decimals.setValue(0)
            elif nf == "decimal_2":
                self._cmb_number_cat.setCurrentIndex(1)
                self._spn_nf_decimals.setValue(2)
            elif nf == "decimal_3":
                self._cmb_number_cat.setCurrentIndex(1)
                self._spn_nf_decimals.setValue(3)
            elif nf.startswith("#,##0."):
                self._cmb_number_cat.setCurrentIndex(1)
                decimals = len(nf) - nf.rfind("0") - 1
                self._spn_nf_decimals.setValue(max(0, min(10, decimals)))
            elif nf == "text":
                self._cmb_number_cat.setCurrentIndex(4)  # 文本
            elif nf == "percent":
                self._cmb_number_cat.setCurrentIndex(3)  # 百分比
                self._spn_nf_decimals.setValue(2)
            elif nf.endswith("%"):
                self._cmb_number_cat.setCurrentIndex(3)  # 百分比
                # 解析小数点位数，如 0.000% → 3
                core = nf.rstrip("%")
                if "." in core:
                    decimals = len(core) - core.rfind("0") - 1
                else:
                    decimals = 0
                self._spn_nf_decimals.setValue(max(0, min(10, decimals)))
            elif nf == "date" or any(d in nf for d in ["yyyy", "mm", "dd", "yy"]):
                self._cmb_number_cat.setCurrentIndex(2)  # 日期
                idx = self._cmb_nf_date.findText(nf)
                if idx >= 0:
                    self._cmb_nf_date.setCurrentIndex(idx)
            else:
                # 自定义格式字符串
                self._cmb_number_cat.setCurrentIndex(5)  # 自定义
                self._txt_nf_custom.setText(nf)
            # 触发类别变更以显示正确的子控件
            self._on_number_cat_changed(self._cmb_number_cat.currentIndex())
        else:
            self._cmb_number_cat.setCurrentIndex(0)
            self._on_number_cat_changed(0)

        self._suppress_update = False

    def _load_db_binding(self):
        """加载数据库绑定信息到第二组面板。"""
        if self._current_row < 0 or self._current_col < 0:
            return
        cd = self._template.get_cell_data(self._current_row, self._current_col)
        qb = cd.query_binding or QueryBinding()

        self._chk_db_enabled.blockSignals(True)
        self._chk_db_enabled.setChecked(qb.enabled)
        self._chk_db_enabled.blockSignals(False)

        self._cmb_query_type.blockSignals(True)
        self._cmb_query_type.setCurrentIndex(0 if qb.query_type == QueryType.SINGLE else 1)
        self._cmb_query_type.blockSignals(False)

        self._cmb_aggregate.blockSignals(True)
        aggs = ["SUM", "COUNT", "AVG", "MAX", "MIN"]
        idx = aggs.index(qb.aggregate_func) if qb.aggregate_func in aggs else 0
        self._cmb_aggregate.setCurrentIndex(idx)
        self._cmb_aggregate.blockSignals(False)

        self._txt_table.blockSignals(True)
        self._txt_table.setText(qb.table_name)
        self._txt_table.blockSignals(False)

        self._txt_field.blockSignals(True)
        self._txt_field.setText(qb.field_name)
        self._txt_field.blockSignals(False)

        self._txt_date_ph.blockSignals(True)
        self._txt_date_ph.setText(qb.date_placeholder)
        self._txt_date_ph.blockSignals(False)

        self._txt_filters.blockSignals(True)
        if qb.filters:
            filter_lines = []
            for f in qb.filters:
                filter_lines.append(f"{f.get('field','')} {f.get('op','=')} {f.get('value','')}")
            self._txt_filters.setPlainText("\n".join(filter_lines))
        else:
            self._txt_filters.clear()
        self._txt_filters.blockSignals(False)

        self._update_sql_preview()

    def _get_current_style(self):
        return self._template.get_scope_style(
            self._current_scope, self._current_row, self._current_col
        )

    # ==================================================================
    # 控件变更 → 实时应用到模板
    # ==================================================================
    def _collect_number_format(self):
        """从两级数字格式 UI 收集 number_format 字符串。"""
        categories = ["常规", "数值", "日期", "百分比", "文本", "自定义"]
        cat = categories[self._cmb_number_cat.currentIndex()]
        if cat == "常规":
            return "general"
        if cat == "文本":
            return "text"
        if cat == "数值":
            decimals = self._spn_nf_decimals.value()
            if decimals == 0:
                return "integer"
            if decimals == 2:
                return "decimal_2"
            if decimals == 3:
                return "decimal_3"
            return "#,##0." + "0" * decimals
        if cat == "日期":
            return self._cmb_nf_date.currentText()
        if cat == "百分比":
            decimals = self._spn_nf_decimals.value()
            if decimals == 0:
                return "0%"
            if decimals == 2:
                return "percent"  # 0.00%
            return "0." + "0" * decimals + "%"
        if cat == "自定义":
            txt = self._txt_nf_custom.text().strip()
            return txt if txt else None
        return None

    def _apply_style(self, style: CellStyle):
        """增量应用：只覆盖本次修改的字段（非 None 字段）。

        style 中为 None 的字段会沿用目标单元格/范围原有的样式，
        从而避免把整个左侧面板的设置一股脑全部应用。
        """
        if self._suppress_update:
            return

        # 多单元格选中 → 每个单元格分别 merge
        if len(self._selected_cells) > 1:
            for r, c in self._selected_cells:
                existing = self._template.cell_styles.get((r, c), CellStyle())
                self._template.set_cell_style(r, c, existing.merge(style))
        elif self._current_scope == StyleScope.DEFAULT:
            self._template.default_style = self._template.default_style.merge(style)
        elif self._current_scope == StyleScope.COLUMN and self._current_col >= 0:
            existing = self._template.column_styles.get(self._current_col, CellStyle())
            self._template.set_column_style(self._current_col, existing.merge(style))
        elif self._current_scope == StyleScope.ROW and self._current_row >= 0:
            existing = self._template.row_styles.get(self._current_row, CellStyle())
            self._template.set_row_style(self._current_row, existing.merge(style))
        elif self._current_scope == StyleScope.CELL and self._current_row >= 0 and self._current_col >= 0:
            existing = self._template.cell_styles.get((self._current_row, self._current_col), CellStyle())
            self._template.set_cell_style(self._current_row, self._current_col, existing.merge(style))

        self.style_changed.emit()

    def _collect_db_binding(self) -> QueryBinding:
        """从第二组面板收集数据库绑定。"""
        qb = QueryBinding()
        qb.enabled = self._chk_db_enabled.isChecked()
        qb.query_type = QueryType.SINGLE if self._cmb_query_type.currentIndex() == 0 else QueryType.AGGREGATE
        qb.aggregate_func = self._cmb_aggregate.currentText()
        qb.table_name = self._txt_table.text().strip()
        qb.field_name = self._txt_field.text().strip()
        qb.date_placeholder = self._txt_date_ph.text().strip()

        # 解析筛选条件
        filters = []
        for line in self._txt_filters.toPlainText().strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                filters.append({"field": parts[0], "op": parts[1], "value": parts[2]})
            elif len(parts) == 2:
                filters.append({"field": parts[0], "op": "=", "value": parts[1]})
        qb.filters = filters

        return qb

    def _apply_db_binding(self):
        """将数据库绑定写入模板。"""
        if self._current_row < 0 or self._current_col < 0:
            return
        cd = self._template.get_cell_data(self._current_row, self._current_col)
        cd.query_binding = self._collect_db_binding()
        self._template.set_cell_data(self._current_row, self._current_col, cd)
        self._update_sql_preview()

    def _update_sql_preview(self):
        qb = self._collect_db_binding()
        sql = qb.build_sql("2026-01-01")
        self._lbl_sql_preview.setText(sql if sql else "-")

    # ------------------------------------------------------------------
    # 信号槽
    # ------------------------------------------------------------------
    def _on_cjk_font_changed(self, txt):
        txt = txt.strip()
        if txt:
            self._apply_style(CellStyle(font_family=txt))

    def _on_western_font_changed(self, txt):
        txt = txt.strip()
        if txt:
            self._apply_style(CellStyle(font_family_western=txt))

    def _on_size_changed(self, val):
        self._apply_style(CellStyle(font_size=val))

    def _on_bold_changed(self, _state):
        if self._chk_bold.checkState() == Qt.CheckState.PartiallyChecked:
            return
        self._apply_style(CellStyle(bold=self._chk_bold.isChecked()))

    def _on_italic_changed(self, _state):
        if self._chk_italic.checkState() == Qt.CheckState.PartiallyChecked:
            return
        self._apply_style(CellStyle(italic=self._chk_italic.isChecked()))

    def _on_underline_changed(self, _state):
        if self._chk_underline.checkState() == Qt.CheckState.PartiallyChecked:
            return
        self._apply_style(CellStyle(underline=self._chk_underline.isChecked()))

    def _on_alignment_changed(self, id_):
        align_map = {
            0: int(Qt.AlignmentFlag.AlignLeft),
            1: int(Qt.AlignmentFlag.AlignCenter),
            2: int(Qt.AlignmentFlag.AlignRight),
        }
        if id_ >= 0:
            self._apply_style(CellStyle(alignment=align_map[id_]))

    def _on_valignment_changed(self, id_):
        valign_map = {
            0: int(Qt.AlignmentFlag.AlignTop),
            1: int(Qt.AlignmentFlag.AlignVCenter),
            2: int(Qt.AlignmentFlag.AlignBottom),
        }
        if id_ >= 0:
            self._apply_style(CellStyle(vertical_alignment=valign_map[id_]))

    def _on_fg_color_clicked(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self._btn_fg_color.setStyleSheet(
                f"background-color:{color.name()}; border:1px solid #999; border-radius:3px;"
            )
            self._chk_fg_reset.blockSignals(True)
            self._chk_fg_reset.setChecked(False)
            self._chk_fg_reset.blockSignals(False)
            self._apply_style(CellStyle(fg_color=color.name()))

    def _on_bg_color_clicked(self):
        color = QColorDialog.getColor(QColor("#FFFFFF"))
        if color.isValid():
            self._btn_bg_color.setStyleSheet(
                f"background-color:{color.name()}; border:1px solid #999; border-radius:3px;"
            )
            self._chk_bg_reset.blockSignals(True)
            self._chk_bg_reset.setChecked(False)
            self._chk_bg_reset.blockSignals(False)
            self._apply_style(CellStyle(bg_color=color.name()))

    def _on_fg_reset_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self._btn_fg_color.setStyleSheet(
                "background-color:#000000; border:1px solid #999; border-radius:3px;"
            )
            self._apply_style(CellStyle(fg_color=""))

    def _on_bg_reset_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self._btn_bg_color.setStyleSheet(
                "background-color:#FFFFFF; border:1px solid #999; border-radius:3px;"
            )
            self._apply_style(CellStyle(bg_color=""))

    def _current_border_line_style(self) -> str:
        border_styles = ["solid", "dashed", "dotted", "dash_dot", "double", "none"]
        return border_styles[self._cmb_border_style.currentIndex()]

    def _on_border_style_changed(self):
        """线型变更：更新线型及所有已勾选方向。"""
        line_style = self._current_border_line_style()
        style = CellStyle(border_line_style=line_style if line_style != "none" else None)
        if line_style == "none":
            style.border_top = style.border_bottom = style.border_left = style.border_right = ""
        else:
            if self._chk_border_top.isChecked():
                style.border_top = line_style
            if self._chk_border_bottom.isChecked():
                style.border_bottom = line_style
            if self._chk_border_left.isChecked():
                style.border_left = line_style
            if self._chk_border_right.isChecked():
                style.border_right = line_style
        self._update_border_preview()
        self._apply_style(style)

    def _on_border_width_changed(self, val):
        self._update_border_preview()
        self._apply_style(CellStyle(border_width=val))

    def _on_border_dir_changed(self, side: str):
        """单个方向勾选/取消：只应用该方向。"""
        line_style = self._current_border_line_style()
        chk = getattr(self, f"_chk_border_{side}")
        val = line_style if (chk.isChecked() and line_style != "none") else ""
        self._update_border_preview()
        self._apply_style(CellStyle(**{f"border_{side}": val}))

    def _update_border_preview(self):
        """根据当前边框设置更新预览标签，按方向分别展示。"""
        border_styles = ["solid", "dashed", "dotted", "dash_dot", "double", "none"]
        line_style = border_styles[self._cmb_border_style.currentIndex()]
        # Qt QSS 样式映射（QSS 不支持 dash_dot，用 dashed 代替预览）
        qss_map = {"solid": "solid", "dashed": "dashed", "dotted": "dotted",
                   "dash_dot": "dashed", "double": "double", "none": "none"}
        qss_style = qss_map.get(line_style, "solid")
        width = self._spn_border_width.value()
        width_str = f"{width:.1f}".rstrip('0').rstrip('.')  # 去除多余小数点
        top_on = self._chk_border_top.isChecked()
        bottom_on = self._chk_border_bottom.isChecked()
        left_on = self._chk_border_left.isChecked()
        right_on = self._chk_border_right.isChecked()
        any_on = top_on or bottom_on or left_on or right_on

        if line_style == "none" or not any_on:
            self._lbl_border_preview.setStyleSheet(
                "border:2px solid #E0E3E8; border-radius:4px; background:#FAFBFC; color:#A0A8B4;"
            )
            self._lbl_border_preview.setText("无边框")
            return

        # 按方向构建 QSS
        parts = ["border-radius:4px; background:#FAFBFC; color:#2C3E50; font-weight:bold;"]
        side_props = [
            ("top", top_on), ("bottom", bottom_on),
            ("left", left_on), ("right", right_on),
        ]
        for side, on in side_props:
            if on:
                parts.append(f"border-{side}:{width_str}px {qss_style} #5B9BD5;")
            else:
                parts.append(f"border-{side}:{width_str}px none transparent;")

        self._lbl_border_preview.setStyleSheet(" ".join(parts))

        style_names = {"solid": "实线", "dashed": "虚线", "dotted": "点线", "dash_dot": "点划线", "double": "双线"}
        sides = []
        if top_on: sides.append("上")
        if bottom_on: sides.append("下")
        if left_on: sides.append("左")
        if right_on: sides.append("右")
        self._lbl_border_preview.setText(f"{style_names.get(line_style, '')} {width_str}px  [{''.join(sides)}]")

    def _on_number_cat_changed(self, idx: int):
        """切换数字格式类别，显示/隐藏对应的子选项。"""
        categories = ["常规", "数值", "日期", "百分比", "文本", "自定义"]
        cat = categories[idx] if 0 <= idx < len(categories) else "常规"
        # 全部隐藏
        self._nf_decimals_row.hide()
        self._cmb_nf_date.hide()
        self._txt_nf_custom.hide()
        self._lbl_nf_hint.hide()
        if cat in ("数值", "百分比"):
            self._nf_decimals_row.show()
        elif cat == "日期":
            self._cmb_nf_date.show()
        elif cat == "自定义":
            self._txt_nf_custom.show()
        else:
            self._lbl_nf_hint.setText("无任何特定数字格式" if cat == "常规" else "文本格式")
            self._lbl_nf_hint.show()
        if not self._suppress_update:
            self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _on_number_format_changed(self):
        self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _on_db_enabled_changed(self, _state):
        self._apply_db_binding()

    def _on_db_config_changed(self):
        self._apply_db_binding()

    def _on_apply_clicked(self):
        btn = self.sender()
        scope_name = btn.text()
        scope_map = {
            "单元格": StyleScope.CELL,
            "本行": StyleScope.ROW,
            "本列": StyleScope.COLUMN,
            "全局": StyleScope.DEFAULT,
        }
        self._current_scope = scope_map.get(scope_name, StyleScope.DEFAULT)
        self._load_style_for_current_scope()

    def _on_reset_clicked(self):
        """清除当前范围的样式。"""
        if self._current_scope == StyleScope.DEFAULT:
            self._template.default_style = CellStyle(
                font_family="宋体", font_family_western="Times New Roman", font_size=10,
                alignment=int(Qt.AlignmentFlag.AlignCenter),
            )
        elif self._current_scope == StyleScope.COLUMN and self._current_col >= 0:
            self._template.clear_column_style(self._current_col)
        elif self._current_scope == StyleScope.ROW and self._current_row >= 0:
            self._template.clear_row_style(self._current_row)
        elif self._current_scope == StyleScope.CELL and self._current_row >= 0 and self._current_col >= 0:
            self._template.clear_cell_style(self._current_row, self._current_col)

        self._load_style_for_current_scope()
        self.style_changed.emit()

    def _on_clear_all_clicked(self):
        self._template.clear_all()
        self._template.default_style = CellStyle(
            font_family="宋体", font_family_western="Times New Roman", font_size=10,
            alignment=int(Qt.AlignmentFlag.AlignCenter),
        )
        self._load_style_for_current_scope()
        self._load_db_binding()
        self.style_changed.emit()
