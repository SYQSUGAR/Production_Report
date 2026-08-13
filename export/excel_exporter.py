"""Excel 导出器（增强版）—— 完整复现模板全部格式。

新增功能:
  - 合并单元格渲染
  - 边框样式（上/下/左/右/全边框）
  - 数字格式（整数/两位小数/百分比/日期）
  - 静态文本写入 + 数据库绑定自动查询
  - 自定义行高 / 列宽
"""

from pathlib import Path
from typing import Optional, Callable

import openpyxl
from openpyxl.styles import (
    Font, Alignment, PatternFill, Border, Side, NamedStyle, numbers
)
from openpyxl.utils import get_column_letter

from models.template_model import (
    TemplateModel, CellStyle, BorderStyle, NumberFormat
)
from PyQt6.QtCore import Qt


# 数字格式映射
_NUMBER_FORMAT_MAP = {
    "general": "General",
    "text": "@",
    "integer": "#,##0",
    "decimal_2": "#,##0.00",
    "decimal_3": "#,##0.000",
    "percent": "0.00%",
    "date": "yyyy-mm-dd",
}


class ExcelExporter:
    """根据 TemplateModel + 数据导出 Excel，完整复现全部格式。"""

    @staticmethod
    def _qt_align_to_openpyxl(alignment_int: int | None) -> str:
        """将 Qt alignment 转为 openpyxl horizontal alignment 字符串。"""
        if alignment_int is None:
            return "center"
        a = Qt.AlignmentFlag(alignment_int)
        if a == Qt.AlignmentFlag.AlignLeft:
            return "left"
        elif a == Qt.AlignmentFlag.AlignRight:
            return "right"
        return "center"

    @staticmethod
    def _qt_valign_to_openpyxl(alignment_int: int | None) -> str:
        """将 Qt alignment 转为 openpyxl vertical alignment 字符串。"""
        if alignment_int is None:
            return "center"
        a = Qt.AlignmentFlag(alignment_int)
        if a == Qt.AlignmentFlag.AlignTop:
            return "top"
        elif a == Qt.AlignmentFlag.AlignBottom:
            return "bottom"
        return "center"

    @staticmethod
    def _make_border(
        top: Optional[str] = None,
        bottom: Optional[str] = None,
        left: Optional[str] = None,
        right: Optional[str] = None,
        line_style: Optional[str] = None,
        width: Optional[int] = None,
    ) -> Border:
        """根据四个方向的样式构建 Border。"""
        # openpyxl 线型映射
        style_map = {
            "solid": "thin", "dashed": "dashed", "dotted": "dotted",
            "dash_dot": "dashDot", "double": "double",
            "thin": "thin", "medium": "medium", "thick": "thick",
        }
        base_style = style_map.get(line_style or "solid", "thin")
        color = "000000"

        sides = {}
        for direction, enabled in [("left", left), ("right", right),
                                    ("top", top), ("bottom", bottom)]:
            if enabled:
                sides[direction] = Side(style=base_style, color=color)
        return Border(**sides) if sides else Border()

    @classmethod
    def export(
        cls,
        template: TemplateModel,
        data: list[list[str]],
        filepath: str,
        query_callback: Optional[Callable[[int, int], Optional[str]]] = None,
    ):
        """导出 Excel 文件。

        Args:
            template: 样式模板。
            data: 二维数据列表。
            filepath: 输出 .xlsx 路径。
            query_callback: 可选，数据库查询回调 (row, col) -> str。
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = template.template_name or "Sheet1"

        if not data or template.rows == 0 or template.cols == 0:
            wb.save(filepath)
            return

        rows = template.rows
        cols = template.cols

        # 写入单元格数据和样式
        for r_idx in range(rows):
            row_num = r_idx + 1
            for c_idx in range(cols):
                col_num = c_idx + 1

                # 获取数据内容（优先使用 cell_data 中的 static_text）
                cell_data = template.get_cell_data(r_idx, c_idx)
                cell_text = ""
                if cell_data.static_text:
                    cell_text = cell_data.static_text
                elif (cell_data.query_binding and cell_data.query_binding.enabled and
                      query_callback):
                    # 执行数据库查询
                    db_result = query_callback(r_idx, c_idx)
                    if db_result is not None:
                        cell_text = db_result
                elif r_idx < len(data) and c_idx < len(data[r_idx]):
                    cell_text = data[r_idx][c_idx]

                # 尝试将文本转为数值（根据数字格式）
                style = template.get_effective_style(r_idx, c_idx)
                num_fmt = style.number_format
                if num_fmt in (NumberFormat.INTEGER.value, NumberFormat.DECIMAL_2.value,
                               "decimal_3"):
                    try:
                        val = float(cell_text.replace(",", ""))
                        if num_fmt == NumberFormat.INTEGER.value:
                            val = int(val)
                        cell = ws.cell(row=row_num, column=col_num, value=val)
                    except (ValueError, AttributeError):
                        cell = ws.cell(row=row_num, column=col_num, value=cell_text)
                else:
                    cell = ws.cell(row=row_num, column=col_num, value=cell_text)

                cls._apply_style(cell, template, r_idx, c_idx)

        # 合并单元格
        for mr in template.merge_ranges:
            try:
                ws.merge_cells(
                    start_row=mr.top_row + 1,
                    start_column=mr.left_col + 1,
                    end_row=mr.bottom_row + 1,
                    end_column=mr.right_col + 1,
                )
            except Exception:
                pass  # 忽略合并冲突

        # 自定义列宽
        for c_idx, width in template.col_widths.items():
            col_letter = get_column_letter(c_idx + 1)
            ws.column_dimensions[col_letter].width = width

        # 自定义行高
        for r_idx, height in template.row_heights.items():
            ws.row_dimensions[r_idx + 1].height = height

        # 默认自适应列宽（未手动设置宽度的列）
        for c_idx in range(cols):
            if c_idx not in template.col_widths:
                max_len = 0
                for r_idx in range(rows):
                    text = ""
                    if r_idx < len(data) and c_idx < len(data[r_idx]):
                        text = str(data[r_idx][c_idx])
                    cd = template.get_cell_data(r_idx, c_idx)
                    if cd.static_text:
                        text = cd.static_text
                    length = sum(2 if ord(ch) > 127 else 1 for ch in text)
                    max_len = max(max_len, length)
                col_letter = get_column_letter(c_idx + 1)
                ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

        wb.save(filepath)

    @classmethod
    def _apply_style(cls, cell, template: TemplateModel, row: int, col: int):
        """将模板的合并样式写到 openpyxl cell（包含边框和数字格式）。"""
        style = template.get_effective_style(row, col)

        # 字体（openpyxl 不支持中西文分离字体，使用 CJK 字体为主字体）
        font_kwargs = {}
        if style.font_family:
            font_kwargs["name"] = style.font_family
        if style.font_size:
            font_kwargs["size"] = style.font_size
        if style.bold is not None:
            font_kwargs["bold"] = style.bold
        if style.italic is not None:
            font_kwargs["italic"] = style.italic
        if style.underline is not None:
            font_kwargs["underline"] = "single" if style.underline else None
        if style.fg_color:
            font_kwargs["color"] = style.fg_color.lstrip("#")
        cell.font = Font(**font_kwargs)

        # 对齐
        halign = cls._qt_align_to_openpyxl(style.alignment)
        valign = cls._qt_valign_to_openpyxl(style.vertical_alignment)
        cell.alignment = Alignment(horizontal=halign, vertical=valign,
                                   wrap_text=True)

        # 背景
        if style.bg_color:
            cell.fill = PatternFill(start_color=style.bg_color.lstrip("#"),
                                    end_color=style.bg_color.lstrip("#"),
                                    fill_type="solid")

        # 边框
        cell.border = cls._make_border(
            top=style.border_top,
            bottom=style.border_bottom,
            left=style.border_left,
            right=style.border_right,
            line_style=style.border_line_style,
            width=style.border_width,
        )

        # 数字格式（支持自定义格式字符串）
        if style.number_format:
            fmt = _NUMBER_FORMAT_MAP.get(style.number_format, style.number_format)
            cell.number_format = fmt
