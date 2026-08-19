"""模板编辑页左右独立属性栏。"""

from ui.style_panel import StylePanel
from models.template_model import CellStyle


class StyleOnlyPanel(StylePanel):
    """左侧：仅保留字体、颜色、边框、对齐和数字格式。"""

    def __init__(self, template, parent=None):
        super().__init__(template, parent=parent, metadata_provider=None)
        self.setMinimumWidth(285)
        self.setMaximumWidth(360)

        # StylePanel 的第 2 页是数据库绑定；左侧彻底移除。
        if self._toolbox.count() > 1:
            self._toolbox.removeItem(1)

        # 旧的“应用样式到”和清除按钮不再显示。
        for group in self.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QGroupBox']).QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QPushButton']).QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

        # 数字格式与数据库查询完全解耦。
        self._lbl_nf_db_lock.hide()
        self._cmb_number_cat.setEnabled(True)
        self._nf_sub_widget.setEnabled(True)
        self._nf_grp.setToolTip("")

    def _on_number_cat_changed(self, idx: int):
        categories = ["常规", "数值", "日期", "百分比", "文本", "自定义"]
        cat = categories[idx] if 0 <= idx < len(categories) else "常规"
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
        if not self._suppress_update:
            self._apply_style(CellStyle(number_format=self._collect_number_format()))

    def _update_db_ui_state(self):
        # 隐藏的数据库页仍会在基类内部调用此函数，但绝不能锁住左侧数字格式。
        super()._update_db_ui_state()
        self._cmb_number_cat.setEnabled(True)
        self._nf_sub_widget.setEnabled(True)
        self._lbl_nf_db_lock.hide()
        self._nf_grp.setToolTip("")


class DatabaseBindingPanel(StylePanel):
    """右侧：仅保留数据库绑定和 SQL 编辑。"""

    def __init__(self, template, parent=None, metadata_provider=None):
        super().__init__(template, parent=parent, metadata_provider=metadata_provider)
        self.setMinimumWidth(360)
        self.setMaximumWidth(500)

        # 第 1 页是样式；右侧彻底移除，只显示数据库绑定。
        if self._toolbox.count() > 0:
            self._toolbox.removeItem(0)

        for group in self.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QGroupBox']).QGroupBox):
            if group.title() == "应用样式到":
                group.hide()
        for button in self.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QPushButton']).QPushButton):
            if button.text() in ("清除当前范围", "清除全部", "清除"):
                button.hide()

    def refresh_template(self, template):
        self._template = template
