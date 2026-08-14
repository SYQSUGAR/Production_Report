"""样式配置面板（增强版）—— 三组可折叠配置区域。

第一组：字体、底色、对齐、边框、数字格式
第二组：数据库绑定开关与配置
第三组：合并范围查看、备注、行列尺寸
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QButtonGroup,
    QColorDialog, QFrame, QSizePolicy, QScrollArea, QToolBox,
    QTextEdit, QLineEdit, QTabWidget, QListWidget, QListWidgetItem, QCompleter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase

from models.template_model import (
    TemplateModel, CellStyle, StyleScope, BorderStyle, NumberFormat, CellData,
)
from models.db_config import (
    QueryBinding, QueryType, SQL_OPERATORS, SQL_OPERATOR_LABELS, parse_sql_to_binding,
)


_SCOPE_MAP = {
    "当前单元格": StyleScope.CELL,
    "当前行": StyleScope.ROW,
    "当前列": StyleScope.COLUMN,
    "全局默认": StyleScope.DEFAULT,
}


class StylePanel(QScrollArea):
    """可滚动的样式配置面板，使用 QToolBox 实现三组折叠。"""

    style_changed = pyqtSignal()  # 通知外部刷新预览
    style_transaction = pyqtSignal(object)  # 一次可撤销的批量样式变更

    def __init__(self, template: TemplateModel, parent=None, metadata_provider=None):
        super().__init__(parent)
        self._template = template
        self._metadata_provider = metadata_provider
        self._db_metadata: dict[str, list[str]] = {}
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
        cr1.addWidget(self._btn_fg_color)
        cr1.addStretch()
        cl.addLayout(cr1)

        cr2 = QHBoxLayout()
        cr2.addWidget(QLabel("背景色:"))
        self._btn_bg_color = QPushButton()
        self._btn_bg_color.setFixedSize(28, 28)
        self._btn_bg_color.setStyleSheet("background-color:#FFFFFF; border:1px solid #999; border-radius:3px;")
        self._btn_bg_color.clicked.connect(self._on_bg_color_clicked)
        cr2.addWidget(self._btn_bg_color)
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
        self._nf_grp = QGroupBox("数字格式")
        nf_lay = QVBoxLayout(self._nf_grp)
        self._lbl_nf_db_lock = QLabel("已启用数据库查询")
        self._lbl_nf_db_lock.setStyleSheet("color:#B06000; font-weight:bold;")
        self._lbl_nf_db_lock.hide()
        nf_lay.addWidget(self._lbl_nf_db_lock)
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

        lay.addWidget(self._nf_grp)

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

        # 编写方式
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("编写方式:"))
        self._cmb_sql_mode = QComboBox()
        self._cmb_sql_mode.addItems(["条件构建", "手动 SQL"])
        self._cmb_sql_mode.currentIndexChanged.connect(self._on_sql_mode_changed)
        mode_row.addWidget(self._cmb_sql_mode, 1)
        lay.addLayout(mode_row)
        self._chk_sql_sync = QCheckBox("自动同步两种查询方式")
        self._chk_sql_sync.setToolTip("开启后：切换到 SQL 会自动生成；切回可视化时仅同步可安全解析的简单 SQL")
        self._chk_sql_sync.stateChanged.connect(self._on_db_config_changed)
        lay.addWidget(self._chk_sql_sync)

        # 条件构建模式容器
        self._builder_widget = QWidget()
        bl = QVBoxLayout(self._builder_widget)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)

        qt_row = QHBoxLayout()
        qt_row.addWidget(QLabel("查询类型:"))
        self._cmb_query_type = QComboBox()
        self._cmb_query_type.addItems(["单值查询", "聚合查询"])
        self._cmb_query_type.currentIndexChanged.connect(self._on_query_type_changed)
        qt_row.addWidget(self._cmb_query_type, 1)
        bl.addLayout(qt_row)

        self._agg_widget = QWidget()
        agg_row = QHBoxLayout(self._agg_widget)
        agg_row.setContentsMargins(0, 0, 0, 0)
        agg_row.addWidget(QLabel("聚合:"))
        self._cmb_aggregate = QComboBox()
        self._cmb_aggregate.addItems(["SUM", "COUNT", "AVG", "MAX", "MIN"])
        self._cmb_aggregate.currentIndexChanged.connect(self._on_db_config_changed)
        agg_row.addWidget(self._cmb_aggregate, 1)
        bl.addWidget(self._agg_widget)

        tbl_row = QHBoxLayout()
        tbl_row.addWidget(QLabel("数据表:"))
        self._cmb_table = QComboBox(); self._cmb_table.setEditable(True)
        self._txt_table = self._cmb_table.lineEdit()
        self._txt_table.setPlaceholderText("选择或输入数据表")
        self._txt_table.textChanged.connect(self._on_db_config_changed)
        self._cmb_table.currentTextChanged.connect(self._on_source_table_changed)
        tbl_row.addWidget(self._cmb_table, 1)
        self._btn_refresh_metadata = QPushButton("读取数据库")
        self._btn_refresh_metadata.clicked.connect(self._refresh_db_metadata)
        tbl_row.addWidget(self._btn_refresh_metadata)
        bl.addLayout(tbl_row)
        self._lbl_metadata_state = QLabel("尚未读取数据库结构；仍可直接输入")
        self._lbl_metadata_state.setStyleSheet("color:#777;")
        bl.addWidget(self._lbl_metadata_state)

        fld_row = QHBoxLayout()
        fld_row.addWidget(QLabel("字段:"))
        self._cmb_field = QComboBox(); self._cmb_field.setEditable(True)
        self._txt_field = self._cmb_field.lineEdit()
        self._txt_field.setPlaceholderText("选择或输入返回字段")
        self._txt_field.textChanged.connect(self._on_db_config_changed)
        fld_row.addWidget(self._cmb_field, 1)
        bl.addLayout(fld_row)

        self._result_options_grp = QGroupBox("返回结果设置")
        result_options_lay = QVBoxLayout(self._result_options_grp)
        self._chk_distinct = QCheckBox("结果去重（删除完全重复的结果行）")
        self._chk_distinct.stateChanged.connect(self._on_db_config_changed)
        result_options_lay.addWidget(self._chk_distinct)

        result_options_lay.addWidget(QLabel("多字段返回（可选；添加后替代上面的主返回字段）:"))
        select_row = QHBoxLayout()
        self._cmb_select_field = QComboBox(); self._cmb_select_field.setEditable(True)
        self._cmb_select_field.lineEdit().setPlaceholderText("选择或输入字段")
        self._cmb_select_aggregate = QComboBox()
        self._cmb_select_aggregate.addItems(["不聚合", "SUM", "COUNT", "AVG", "MAX", "MIN"])
        self._txt_select_alias = QLineEdit(); self._txt_select_alias.setPlaceholderText("别名（可选）")
        select_row.addWidget(self._cmb_select_field, 1)
        select_row.addWidget(self._cmb_select_aggregate)
        select_row.addWidget(self._txt_select_alias, 1)
        result_options_lay.addLayout(select_row)
        select_btn_row = QHBoxLayout()
        btn_add_select = QPushButton("添加返回字段")
        btn_add_select.clicked.connect(self._add_select_field)
        btn_remove_select = QPushButton("删除所选")
        btn_remove_select.clicked.connect(self._remove_select_field)
        select_btn_row.addWidget(btn_add_select); select_btn_row.addWidget(btn_remove_select)
        select_btn_row.addStretch(); result_options_lay.addLayout(select_btn_row)
        self._lst_select_fields = QListWidget(); self._lst_select_fields.setFixedHeight(70)
        result_options_lay.addWidget(self._lst_select_fields)
        bl.addWidget(self._result_options_grp)

        self._chk_use_joins = QCheckBox("启用关联表")
        self._chk_use_joins.stateChanged.connect(self._on_optional_query_changed)
        bl.addWidget(self._chk_use_joins)
        self._lbl_joins = QLabel("关联方式（主表字段 = 关联表字段）:")
        bl.addWidget(self._lbl_joins)
        self._join_widget = QWidget(); join_lay = QVBoxLayout(self._join_widget)
        join_lay.setContentsMargins(0, 0, 0, 0)
        join_top = QHBoxLayout()
        self._cmb_join_type = QComboBox(); self._cmb_join_type.addItems(
            ["LEFT JOIN", "INNER JOIN", "RIGHT JOIN", "FULL JOIN"])
        self._cmb_join_table = QComboBox(); self._cmb_join_table.setEditable(True)
        self._cmb_join_table.lineEdit().setPlaceholderText("选择或输入关联表")
        join_top.addWidget(self._cmb_join_type); join_top.addWidget(self._cmb_join_table, 1)
        join_lay.addLayout(join_top)
        join_fields = QHBoxLayout()
        self._cmb_join_left = QComboBox(); self._cmb_join_left.setEditable(True)
        self._cmb_join_right = QComboBox(); self._cmb_join_right.setEditable(True)
        join_fields.addWidget(self._cmb_join_left, 1); join_fields.addWidget(QLabel("="))
        join_fields.addWidget(self._cmb_join_right, 1); join_lay.addLayout(join_fields)
        for combo in (self._cmb_join_type, self._cmb_join_table,
                      self._cmb_join_left, self._cmb_join_right):
            combo.currentTextChanged.connect(self._on_db_config_changed)
        self._cmb_join_table.currentTextChanged.connect(self._refresh_identifier_choices)
        bl.addWidget(self._join_widget)

        dp_row = QHBoxLayout()
        dp_row.addWidget(QLabel("日期占位符:"))
        self._txt_date_ph = QLineEdit()
        self._txt_date_ph.setPlaceholderText("如: {date}")
        self._txt_date_ph.textChanged.connect(self._on_db_config_changed)
        dp_row.addWidget(self._txt_date_ph, 1)
        bl.addLayout(dp_row)

        bl.addWidget(QLabel("筛选条件 (where / and / or):"))
        self._filters_container = QWidget()
        self._filters_layout = QVBoxLayout(self._filters_container)
        self._filters_layout.setContentsMargins(0, 0, 0, 0)
        self._filters_layout.setSpacing(2)
        bl.addWidget(self._filters_container)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 条件")
        btn_add.clicked.connect(self._add_filter_row)
        btn_del = QPushButton("- 条件")
        btn_del.clicked.connect(self._remove_filter_row)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        bl.addLayout(btn_row)

        self._chk_use_group = QCheckBox("启用分组 / HAVING")
        self._chk_use_group.stateChanged.connect(self._on_optional_query_changed)
        bl.addWidget(self._chk_use_group)
        self._cmb_group_by = QComboBox(); self._cmb_group_by.setEditable(True)
        self._cmb_group_by.lineEdit().setPlaceholderText("选择或输入分组字段")
        bl.addWidget(self._cmb_group_by)
        self._txt_having = QLineEdit(); self._txt_having.setPlaceholderText("聚合筛选 HAVING，如 SUM(p.output) > 100")
        self._txt_having.textChanged.connect(self._on_db_config_changed)
        bl.addWidget(self._txt_having)
        self._chk_use_order = QCheckBox("启用排序")
        self._chk_use_order.stateChanged.connect(self._on_optional_query_changed)
        bl.addWidget(self._chk_use_order)
        order_row = QHBoxLayout()
        self._cmb_order_field = QComboBox(); self._cmb_order_field.setEditable(True)
        self._cmb_order_field.lineEdit().setPlaceholderText("选择或输入排序字段")
        self._cmb_order_direction = QComboBox(); self._cmb_order_direction.addItems(["升序 ASC", "降序 DESC"])
        order_row.addWidget(self._cmb_order_field, 1); order_row.addWidget(self._cmb_order_direction)
        bl.addLayout(order_row)
        limit_row = QHBoxLayout(); limit_row.addWidget(QLabel("最多返回:"))
        self._spn_query_limit = QSpinBox(); self._spn_query_limit.setRange(0, 1000000); self._spn_query_limit.setSpecialValueText("不限制")
        self._spn_query_limit.valueChanged.connect(self._on_db_config_changed)
        limit_row.addWidget(self._spn_query_limit); limit_row.addStretch(); bl.addLayout(limit_row)
        self._cmb_group_by.currentTextChanged.connect(self._on_db_config_changed)
        self._cmb_order_field.currentTextChanged.connect(self._on_db_config_changed)
        self._cmb_order_direction.currentIndexChanged.connect(self._on_db_config_changed)

        lay.addWidget(self._builder_widget)

        # 手动 SQL 模式容器
        self._manual_widget = QWidget()
        ml = QVBoxLayout(self._manual_widget)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(QLabel("SQL 语句:"))
        self._txt_custom_sql = QTextEdit()
        self._txt_custom_sql.setFixedHeight(100)
        self._txt_custom_sql.setPlaceholderText("SELECT ... FROM ... WHERE ...")
        self._txt_custom_sql.textChanged.connect(self._on_manual_sql_changed)
        ml.addWidget(self._txt_custom_sql)
        btn_generate_sql = QPushButton("根据可视化条件生成 / 更新 SQL")
        btn_generate_sql.clicked.connect(self._generate_manual_sql)
        ml.addWidget(btn_generate_sql)
        lay.addWidget(self._manual_widget)

        # SQL 预览（互通）
        lay.addWidget(QLabel("SQL 预览:"))
        self._lbl_sql_preview = QLabel("-")
        self._lbl_sql_preview.setWordWrap(True)
        self._lbl_sql_preview.setStyleSheet("background:#F8F9FC; padding:4px; border-radius:3px; border:1px solid #E0E3E8;")
        lay.addWidget(self._lbl_sql_preview)

        # 验证提示
        self._lbl_sql_validate = QLabel("")
        self._lbl_sql_validate.setWordWrap(True)
        lay.addWidget(self._lbl_sql_validate)

        lay.addStretch()
        self._toolbox.addItem(page, "🗄️  数据库绑定")

        # 初始化条件行
        self._filter_rows: list[dict] = []
        self._add_filter_row()
        self._on_sql_mode_changed(0)
        self._update_db_ui_state()

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
        else:
            self._btn_fg_color.setStyleSheet(
                "background-color:#000000; border:1px solid #999; border-radius:3px;"
            )

        if style.bg_color:
            self._btn_bg_color.setStyleSheet(
                f"background-color:{style.bg_color}; border:1px solid #999; border-radius:3px;"
            )
        else:
            self._btn_bg_color.setStyleSheet(
                "background-color:#FFFFFF; border:1px solid #999; border-radius:3px;"
            )

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
        self._suppress_update = True
        cd = self._template.get_cell_data(self._current_row, self._current_col)
        qb = cd.query_binding or QueryBinding()

        self._chk_db_enabled.blockSignals(True)
        self._chk_db_enabled.setChecked(qb.enabled)
        self._chk_db_enabled.blockSignals(False)

        self._cmb_sql_mode.blockSignals(True)
        self._cmb_sql_mode.setCurrentIndex(1 if qb.sql_mode == "manual" else 0)
        self._cmb_sql_mode.blockSignals(False)
        self._chk_sql_sync.setChecked(qb.sync_modes)
        self._chk_distinct.setChecked(qb.distinct)
        self._chk_use_joins.setChecked(bool(qb.joins))
        self._chk_use_group.setChecked(bool(qb.group_by or qb.having))
        self._chk_use_order.setChecked(bool(qb.order_by))

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
        self._lst_select_fields.clear()
        for field_info in qb.select_fields:
            self._append_select_field_item(field_info)
        join = qb.joins[0] if qb.joins else {}
        self._cmb_join_type.setCurrentText(join.get("type", "LEFT JOIN"))
        self._cmb_join_table.setCurrentText(join.get("table", ""))
        on_parts = join.get("on", "").split("=", 1)
        self._cmb_join_left.setCurrentText(on_parts[0].strip() if on_parts else "")
        self._cmb_join_right.setCurrentText(on_parts[1].strip() if len(on_parts) > 1 else "")
        self._cmb_group_by.setCurrentText(", ".join(qb.group_by))
        self._txt_having.setText(qb.having)
        order = qb.order_by[0] if qb.order_by else {}
        self._cmb_order_field.setCurrentText(order.get("field", ""))
        self._cmb_order_direction.setCurrentIndex(1 if order.get("direction") == "DESC" else 0)
        self._spn_query_limit.setValue(qb.limit or 0)

        self._txt_date_ph.blockSignals(True)
        self._txt_date_ph.setText(qb.date_placeholder)
        self._txt_date_ph.blockSignals(False)

        self._txt_custom_sql.blockSignals(True)
        self._txt_custom_sql.setPlainText(qb.custom_sql)
        self._txt_custom_sql.blockSignals(False)

        # 重建条件行
        self._clear_filter_rows()
        for f in (qb.filters or []):
            self._add_filter_row()
            fr = self._filter_rows[-1]
            fr["field"].setText(f.get("field", ""))
            op = f.get("op", "=")
            if op in SQL_OPERATORS:
                fr["op"].setCurrentIndex(SQL_OPERATORS.index(op))
            fr["value"].setText(f.get("value", ""))
            if len(self._filter_rows) > 1:
                conn = f.get("connector", "and")
                cidx = fr["connector"].findText(conn)
                if cidx >= 0:
                    fr["connector"].setCurrentIndex(cidx)
        if not self._filter_rows:
            self._add_filter_row()

        self._suppress_update = False
        self._on_sql_mode_changed(self._cmb_sql_mode.currentIndex())
        self._update_db_ui_state()
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

        changes = []

        # 多单元格选中 → 每个单元格分别 merge
        if len(self._selected_cells) > 1:
            for r, c in self._selected_cells:
                old = self._template.cell_styles.get((r, c))
                old_copy = old.clone() if old else None
                new = (old or CellStyle()).merge(style)
                if old_copy != new:
                    self._template.set_cell_style(r, c, new)
                    changes.append(("style", r, c, old_copy, new.clone()))
        elif self._current_scope == StyleScope.DEFAULT:
            old = self._template.default_style.clone()
            new = old.merge(style)
            if old != new:
                self._template.default_style = new
                changes.append(("default_style", old, new.clone()))
        elif self._current_scope == StyleScope.COLUMN and self._current_col >= 0:
            old = self._template.column_styles.get(self._current_col)
            old_copy = old.clone() if old else None
            new = (old or CellStyle()).merge(style)
            if old_copy != new:
                self._template.set_column_style(self._current_col, new)
                changes.append(("column_style", self._current_col, old_copy, new.clone()))
        elif self._current_scope == StyleScope.ROW and self._current_row >= 0:
            old = self._template.row_styles.get(self._current_row)
            old_copy = old.clone() if old else None
            new = (old or CellStyle()).merge(style)
            if old_copy != new:
                self._template.set_row_style(self._current_row, new)
                changes.append(("row_style", self._current_row, old_copy, new.clone()))
        elif self._current_scope == StyleScope.CELL and self._current_row >= 0 and self._current_col >= 0:
            old = self._template.cell_styles.get((self._current_row, self._current_col))
            old_copy = old.clone() if old else None
            new = (old or CellStyle()).merge(style)
            if old_copy != new:
                self._template.set_cell_style(self._current_row, self._current_col, new)
                changes.append(("style", self._current_row, self._current_col, old_copy, new.clone()))

        if changes:
            self.style_transaction.emit(changes)
        self.style_changed.emit()

    def _collect_db_binding(self) -> QueryBinding:
        """从第二组面板收集数据库绑定。"""
        qb = QueryBinding()
        qb.enabled = self._chk_db_enabled.isChecked()
        qb.sql_mode = "manual" if self._cmb_sql_mode.currentIndex() == 1 else "builder"
        qb.query_type = QueryType.SINGLE if self._cmb_query_type.currentIndex() == 0 else QueryType.AGGREGATE
        qb.aggregate_func = self._cmb_aggregate.currentText()
        qb.table_name = self._txt_table.text().strip()
        qb.field_name = self._txt_field.text().strip()
        qb.date_placeholder = self._txt_date_ph.text().strip()
        qb.custom_sql = self._txt_custom_sql.toPlainText().strip()
        qb.sync_modes = self._chk_sql_sync.isChecked()
        qb.distinct = self._chk_distinct.isChecked()
        qb.select_fields = []
        for index in range(self._lst_select_fields.count()):
            qb.select_fields.append(dict(self._lst_select_fields.item(index).data(Qt.ItemDataRole.UserRole)))
        qb.joins = []
        if self._chk_use_joins.isChecked():
            join_table = self._cmb_join_table.currentText().strip()
            left = self._cmb_join_left.currentText().strip()
            right = self._cmb_join_right.currentText().strip()
            if join_table and left and right:
                qb.joins.append({"type": self._cmb_join_type.currentText(),
                                 "table": join_table, "on": f"{left} = {right}"})
        qb.group_by = ([x.strip() for x in self._cmb_group_by.currentText().split(",") if x.strip()]
                       if self._chk_use_group.isChecked() else [])
        qb.having = self._txt_having.text().strip() if self._chk_use_group.isChecked() else ""
        qb.order_by = []
        if self._chk_use_order.isChecked():
            field = self._cmb_order_field.currentText().strip()
            if field:
                qb.order_by.append({"field": field,
                                    "direction": "DESC" if self._cmb_order_direction.currentIndex() else "ASC"})
        qb.limit = self._spn_query_limit.value() or None

        # 收集条件行
        filters = []
        for i, fr in enumerate(self._filter_rows):
            field = fr["field"].text().strip()
            value = fr["value"].text().strip()
            if not field and not value:
                continue
            op = SQL_OPERATORS[fr["op"].currentIndex()]
            connector = "where" if i == 0 else fr["connector"].currentText()
            filters.append({"connector": connector, "field": field, "op": op, "value": value})
        qb.filters = filters

        return qb

    def _apply_db_binding(self):
        """将数据库绑定写入模板。"""
        if self._suppress_update:
            return
        if self._current_row < 0 or self._current_col < 0:
            return
        cd = self._template.get_cell_data(self._current_row, self._current_col)
        cd.query_binding = self._collect_db_binding()
        self._template.set_cell_data(self._current_row, self._current_col, cd)
        self._update_sql_preview()

    def _validate_sql(self, sql: str) -> str:
        """简单校验 SQL，返回错误信息（空字符串表示正确）。"""
        if not sql:
            return "SQL 为空"
        upper = sql.upper().strip()
        if not upper.startswith("SELECT"):
            return "SQL 必须以 SELECT 开头"
        if sql.count("(") != sql.count(")"):
            return "括号不匹配"
        if " FROM " not in upper:
            return "缺少 FROM 子句"
        return ""

    def _update_sql_preview(self):
        qb = self._collect_db_binding()
        if not qb.enabled:
            self._lbl_sql_preview.setText("（未启用数据库绑定）")
            self._lbl_sql_validate.setText("")
            return
        sql = qb.build_sql("2026-01-01")
        if not sql:
            self._lbl_sql_preview.setText("（请填写字段/数据表或 SQL 语句）")
            self._lbl_sql_validate.setText("")
            return
        self._lbl_sql_preview.setText(sql)
        err = self._validate_sql(sql)
        if err:
            self._lbl_sql_validate.setText(f"⚠ {err}")
            self._lbl_sql_validate.setStyleSheet("color:#D93025;")
        else:
            self._lbl_sql_validate.setText("✓ SQL 语法正确")
            self._lbl_sql_validate.setStyleSheet("color:#188038;")

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
            self._apply_style(CellStyle(fg_color=color.name()))

    def _on_bg_color_clicked(self):
        color = QColorDialog.getColor(QColor("#FFFFFF"))
        if color.isValid():
            self._btn_bg_color.setStyleSheet(
                f"background-color:{color.name()}; border:1px solid #999; border-radius:3px;"
            )
            self._apply_style(CellStyle(bg_color=color.name()))

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
        if (not self._suppress_update
                and not (hasattr(self, "_chk_db_enabled") and self._chk_db_enabled.isChecked())):
            self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _on_number_format_changed(self):
        if hasattr(self, "_chk_db_enabled") and self._chk_db_enabled.isChecked():
            return
        self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _on_db_enabled_changed(self, _state):
        self._update_db_ui_state()
        if self._chk_db_enabled.isChecked() and not self._db_metadata:
            self._refresh_db_metadata()
        self._apply_db_binding()

    @staticmethod
    def _set_combo_choices(combo: QComboBox, choices: list[str]):
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(choices)
        combo.setCurrentText(current)
        if combo.isEditable() and combo.completer():
            combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.blockSignals(False)

    def _refresh_db_metadata(self):
        provider = self._metadata_provider
        metadata = provider("default") if provider else {}
        self._db_metadata = metadata or {}
        tables = sorted(self._db_metadata, key=str.lower)
        self._set_combo_choices(self._cmb_table, tables)
        self._set_combo_choices(self._cmb_join_table, tables)
        self._refresh_identifier_choices()
        if tables:
            column_count = sum(len(items) for items in self._db_metadata.values())
            self._lbl_metadata_state.setText(
                f"已读取 {len(tables)} 个数据表、{column_count} 个字段；可输入文字筛选")
            self._lbl_metadata_state.setStyleSheet("color:#287A3D;")
        else:
            self._lbl_metadata_state.setText("未读取到数据库结构；下拉栏为空，但仍可手动输入")
            self._lbl_metadata_state.setStyleSheet("color:#B06000;")

    def _on_source_table_changed(self, _text=""):
        self._refresh_identifier_choices()

    def _refresh_identifier_choices(self, _text=""):
        source_parts = self._cmb_table.currentText().strip().split()
        joined_parts = self._cmb_join_table.currentText().strip().split()
        source = source_parts[0] if source_parts else ""
        joined = joined_parts[0] if joined_parts else ""
        source_columns = self._db_metadata.get(source, [])
        joined_columns = self._db_metadata.get(joined, [])
        source_alias = source_parts[-1] if source_parts else ""
        join_alias = joined_parts[-1] if joined_parts else ""
        all_fields = list(source_columns)
        qualified_source = [f"{source_alias}.{name}" for name in source_columns]
        qualified_join = [f"{join_alias}.{name}" for name in joined_columns]
        all_qualified = qualified_source + qualified_join
        self._set_combo_choices(self._cmb_field, all_fields)
        self._set_combo_choices(self._cmb_join_left, qualified_source)
        self._set_combo_choices(self._cmb_join_right, qualified_join)
        self._set_combo_choices(self._cmb_group_by, all_qualified or all_fields)
        self._set_combo_choices(self._cmb_order_field, all_qualified or all_fields)
        self._set_combo_choices(self._cmb_select_field, all_qualified or all_fields)
        for row in self._filter_rows:
            self._set_combo_choices(row["field_combo"], all_qualified or all_fields)

    def _append_select_field_item(self, info: dict):
        field = info.get("field", "").strip()
        if not field:
            return
        aggregate = info.get("aggregate", "").strip().upper()
        alias = info.get("alias", "").strip()
        expression = f"{aggregate}({field})" if aggregate else field
        item = QListWidgetItem(expression + (f"  →  {alias}" if alias else ""))
        item.setData(Qt.ItemDataRole.UserRole,
                     {"field": field, "aggregate": aggregate, "alias": alias})
        self._lst_select_fields.addItem(item)

    def _add_select_field(self):
        self._append_select_field_item({
            "field": self._cmb_select_field.currentText(),
            "aggregate": ("" if self._cmb_select_aggregate.currentIndex() == 0
                          else self._cmb_select_aggregate.currentText()),
            "alias": self._txt_select_alias.text(),
        })
        self._txt_select_alias.clear()
        self._apply_db_binding()

    def _remove_select_field(self):
        row = self._lst_select_fields.currentRow()
        if row >= 0:
            self._lst_select_fields.takeItem(row)
            self._apply_db_binding()

    def _on_query_type_changed(self, _idx):
        self._update_db_ui_state()
        self._apply_db_binding()

    def _on_optional_query_changed(self, _state):
        self._update_db_ui_state()
        self._apply_db_binding()

    def _update_db_ui_state(self):
        """Keep database-query controls visually consistent with their switches."""
        enabled = self._chk_db_enabled.isChecked()

        self._cmb_sql_mode.setEnabled(enabled)
        self._chk_sql_sync.setEnabled(enabled)
        self._builder_widget.setEnabled(enabled)
        self._manual_widget.setEnabled(enabled)

        # A single-value query has no global aggregation step.  Hiding this row
        # keeps the form focused while retaining the setting for aggregate mode.
        self._agg_widget.setVisible(self._cmb_query_type.currentIndex() == 1)

        for checkbox in (self._chk_use_joins, self._chk_use_group, self._chk_use_order):
            checkbox.setEnabled(enabled)

        use_joins = enabled and self._chk_use_joins.isChecked()
        self._lbl_joins.setEnabled(use_joins)
        self._join_widget.setEnabled(use_joins)

        use_group = enabled and self._chk_use_group.isChecked()
        self._cmb_group_by.setEnabled(use_group)
        self._txt_having.setEnabled(use_group)

        use_order = enabled and self._chk_use_order.isChecked()
        self._cmb_order_field.setEnabled(use_order)
        self._cmb_order_direction.setEnabled(use_order)

        # Keep the group title and explanation readable; only the editable
        # number-format controls are locked while the cell is database-driven.
        self._cmb_number_cat.setEnabled(not enabled)
        self._nf_sub_widget.setEnabled(not enabled)
        self._lbl_nf_db_lock.setVisible(enabled)
        self._nf_grp.setToolTip("已启用数据库查询" if enabled else "")

    def _on_db_config_changed(self):
        self._apply_db_binding()

    def _on_manual_sql_changed(self):
        self._apply_db_binding()

    # ------------------------------------------------------------------
    # 条件构建器
    # ------------------------------------------------------------------
    def _add_filter_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)

        connector = QComboBox()
        connector.setFixedWidth(52)
        if not self._filter_rows:
            connector.addItems(["where"])
            connector.setEnabled(False)
        else:
            connector.addItems(["and", "or"])

        field_combo = QComboBox(); field_combo.setEditable(True)
        field = field_combo.lineEdit()
        field.setPlaceholderText("选择或输入筛选字段")

        op = QComboBox()
        op.addItems([SQL_OPERATOR_LABELS[o] for o in SQL_OPERATORS])
        op.setFixedWidth(72)

        value = QLineEdit()
        value.setPlaceholderText("值")

        h.addWidget(connector)
        h.addWidget(field_combo, 1)
        h.addWidget(op)
        h.addWidget(value, 1)

        self._filters_layout.addWidget(row)
        self._filter_rows.append(
            {"widget": row, "connector": connector, "field": field,
             "field_combo": field_combo, "op": op, "value": value}
        )

        if self._db_metadata:
            self._refresh_identifier_choices()

        field.textChanged.connect(self._on_db_config_changed)
        op.currentIndexChanged.connect(self._on_db_config_changed)
        value.textChanged.connect(self._on_db_config_changed)

    def _remove_filter_row(self):
        if len(self._filter_rows) <= 1:
            return
        fr = self._filter_rows.pop()
        fr["widget"].deleteLater()
        self._on_db_config_changed()

    def _clear_filter_rows(self):
        for fr in self._filter_rows:
            fr["widget"].deleteLater()
        self._filter_rows.clear()

    def _parse_sql_to_filters(self, sql: str):
        """手动 SQL → 条件构建器（反向互通）。"""
        info = parse_sql_to_binding(sql)
        if not info.get("safe"):
            self._lbl_sql_validate.setText("⚠ 此 SQL 含 JOIN、子查询、UNION 或其他复杂结构，已保留原 SQL，未覆盖可视化条件")
            self._lbl_sql_validate.setStyleSheet("color:#B06000;")
            return False
        if not info.get("field") and not info.get("filters"):
            return False
        self._txt_table.blockSignals(True)
        self._txt_table.setText(info.get("table", ""))
        self._txt_table.blockSignals(False)
        self._txt_field.blockSignals(True)
        self._txt_field.setText(info.get("field", ""))
        self._txt_field.blockSignals(False)
        agg = info.get("aggregate", "")
        if agg:
            idx = self._cmb_aggregate.findText(agg)
            if idx >= 0:
                self._cmb_aggregate.setCurrentIndex(idx)
            self._cmb_query_type.setCurrentIndex(1)
        else:
            self._cmb_query_type.setCurrentIndex(0)

        self._clear_filter_rows()
        for f in info.get("filters", []):
            self._add_filter_row()
            fr = self._filter_rows[-1]
            fr["field"].setText(f.get("field", ""))
            op = f.get("op", "=")
            if op in SQL_OPERATORS:
                fr["op"].setCurrentIndex(SQL_OPERATORS.index(op))
            fr["value"].setText(f.get("value", ""))
        if not self._filter_rows:
            self._add_filter_row()
        return True

    def _generate_manual_sql(self):
        qb = self._collect_db_binding()
        qb.sql_mode = "builder"
        sql = qb.build_sql("{date}")
        if sql:
            self._txt_custom_sql.blockSignals(True)
            self._txt_custom_sql.setPlainText(sql)
            self._txt_custom_sql.blockSignals(False)
            self._apply_db_binding()

    def _on_sql_mode_changed(self, idx: int):
        """切换编写方式，并在两种方式之间互通。"""
        mode = "manual" if idx == 1 else "builder"
        if mode == "manual":
            self._builder_widget.hide()
            self._manual_widget.show()
            # 条件构建 → 手动 SQL：自动生成 SQL 填入（若手动框为空）
            if self._chk_sql_sync.isChecked() or not self._txt_custom_sql.toPlainText().strip():
                qb = self._collect_db_binding()
                qb.sql_mode = "builder"
                sql = qb.build_sql("2026-01-01")
                if sql:
                    self._txt_custom_sql.blockSignals(True)
                    self._txt_custom_sql.setPlainText(sql)
                    self._txt_custom_sql.blockSignals(False)
        else:
            self._manual_widget.hide()
            self._builder_widget.show()
            # 手动 SQL → 条件构建：解析 SQL 填充条件
            sql = self._txt_custom_sql.toPlainText().strip()
            if sql and self._chk_sql_sync.isChecked():
                self._parse_sql_to_filters(sql)
        self._update_db_ui_state()
        if not self._suppress_update:
            self._update_sql_preview()

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
