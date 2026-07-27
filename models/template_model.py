"""Excel 报表模板数据模型（增强版）。

新增功能:
  - 合并单元格记录 (MergeRange)
  - 每个单元格的专属数据 (CellData)：静态文本、数据库绑定、备注
  - 边框样式支持
  - 数字格式
  - 自定义行高 / 列宽
  - 全局数据库配置存储

样式优先级: Cell > Row > Column > Default（高优先级覆盖低优先级）。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

from .db_config import QueryBinding


class StyleScope(Enum):
    DEFAULT = "default"
    COLUMN = "column"
    ROW = "row"
    CELL = "cell"


class BorderStyle(Enum):
    NONE = "none"
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"
    DOUBLE = "double"


class NumberFormat(Enum):
    GENERAL = "general"       # 常规
    TEXT = "text"             # 文本
    INTEGER = "integer"       # 整数 #,##0
    DECIMAL_2 = "decimal_2"   # 两位小数 #,##0.00
    PERCENT = "percent"       # 百分比 0.00%
    DATE = "date"             # 日期 yyyy-mm-dd


@dataclass
class CellStyle:
    """单个单元格的样式定义，所有字段可选，None 表示沿用上级样式。"""
    font_family: Optional[str] = None       # 中文字体
    font_family_western: Optional[str] = None  # 西文字体
    font_size: Optional[int] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    alignment: Optional[int] = None       # Qt.AlignmentFlag 水平对齐
    vertical_alignment: Optional[int] = None  # Qt.AlignmentFlag 垂直对齐
    bg_color: Optional[str] = None        # 背景色 "#RRGGBB"
    fg_color: Optional[str] = None        # 前景色/字体颜色
    border_top: Optional[str] = None      # 上边框是否启用 "solid" / None
    border_bottom: Optional[str] = None
    border_left: Optional[str] = None
    border_right: Optional[str] = None
    border_line_style: Optional[str] = None  # 线型: solid/dashed/dotted/dash_dot/double
    border_width: Optional[int] = None       # 粗细: 1-5
    number_format: Optional[str] = None   # NumberFormat 值

    def merge(self, other: "CellStyle") -> "CellStyle":
        """将 other 合并到 self 之上 —— other 中非 None 的字段覆盖 self。"""
        result = CellStyle()
        for attr in ("font_family", "font_family_western", "font_size", "bold", "italic",
                     "underline", "alignment", "vertical_alignment", "bg_color", "fg_color",
                     "border_top", "border_bottom", "border_left", "border_right",
                     "border_line_style", "border_width",
                     "number_format"):
            val = getattr(other, attr)
            setattr(result, attr, val if val is not None else getattr(self, attr))
        return result

    def to_qfont(self, base_font: Optional[QFont] = None) -> QFont:
        font = QFont(base_font) if base_font else QFont()
        families = []
        if self.font_family:
            families.append(self.font_family)
        if self.font_family_western:
            families.append(self.font_family_western)
        if families:
            font.setFamilies(families)
        elif self.font_family:
            font.setFamily(self.font_family)
        if self.font_size:
            font.setPointSize(self.font_size)
        if self.bold is not None:
            font.setBold(self.bold)
        if self.italic is not None:
            font.setItalic(self.italic)
        if self.underline is not None:
            font.setUnderline(self.underline)
        return font

    def to_qcolor_bg(self) -> Optional[QColor]:
        return QColor(self.bg_color) if self.bg_color else None

    def to_qcolor_fg(self) -> Optional[QColor]:
        return QColor(self.fg_color) if self.fg_color else None

    def clone(self) -> "CellStyle":
        return CellStyle(
            font_family=self.font_family,
            font_family_western=self.font_family_western,
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            alignment=self.alignment,
            vertical_alignment=self.vertical_alignment,
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            border_top=self.border_top,
            border_bottom=self.border_bottom,
            border_left=self.border_left,
            border_right=self.border_right,
            border_line_style=self.border_line_style,
            border_width=self.border_width,
            number_format=self.number_format,
        )

    def to_dict(self) -> dict:
        result = {}
        for attr in ("font_family", "font_family_western", "font_size", "bold", "italic", "underline",
                     "alignment", "vertical_alignment", "bg_color", "fg_color", "border_top", "border_bottom",
                     "border_left", "border_right", "border_line_style", "border_width", "number_format"):
            val = getattr(self, attr)
            if val is not None:
                result[attr] = val
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "CellStyle":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class MergeRange:
    """合并单元格记录。"""
    top_row: int
    bottom_row: int
    left_col: int
    right_col: int

    def to_dict(self) -> dict:
        return {
            "top_row": self.top_row,
            "bottom_row": self.bottom_row,
            "left_col": self.left_col,
            "right_col": self.right_col,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MergeRange":
        return cls(
            top_row=data["top_row"],
            bottom_row=data["bottom_row"],
            left_col=data["left_col"],
            right_col=data["right_col"],
        )

    def contains(self, row: int, col: int) -> bool:
        return (self.top_row <= row <= self.bottom_row and
                self.left_col <= col <= self.right_col)

    def is_top_left(self, row: int, col: int) -> bool:
        return row == self.top_row and col == self.left_col

    def __hash__(self):
        return hash((self.top_row, self.bottom_row, self.left_col, self.right_col))


@dataclass
class CellData:
    """单个单元格的数据内容。"""
    static_text: str = ""           # 静态文本内容
    query_binding: Optional[QueryBinding] = None  # 数据库查询绑定
    note: str = ""                  # 备注

    def to_dict(self) -> dict:
        return {
            "static_text": self.static_text,
            "query_binding": self.query_binding.to_dict() if self.query_binding else None,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CellData":
        return cls(
            static_text=data.get("static_text", ""),
            query_binding=QueryBinding.from_dict(data["query_binding"]) if data.get("query_binding") else None,
            note=data.get("note", ""),
        )


class TemplateModel:
    """管理整个表格模板的完整配置（样式 + 数据 + 布局）。"""

    def __init__(self, rows: int = 30, cols: int = 10):
        self._rows = rows
        self._cols = cols

        # 默认样式
        self.default_style = CellStyle(
            font_family="宋体",
            font_family_western="Times New Roman",
            font_size=10,
            alignment=int(Qt.AlignmentFlag.AlignCenter),
            border_top=BorderStyle.THIN.value,
            border_bottom=BorderStyle.THIN.value,
            border_left=BorderStyle.THIN.value,
            border_right=BorderStyle.THIN.value,
        )

        # 按维度存储的样式覆盖
        self.column_styles: dict[int, CellStyle] = {}
        self.row_styles: dict[int, CellStyle] = {}
        self.cell_styles: dict[tuple[int, int], CellStyle] = {}

        # 合并单元格集合
        self.merge_ranges: set[MergeRange] = set()

        # 每个单元格的数据 (row, col) -> CellData
        self.cell_data: dict[tuple[int, int], CellData] = {}

        # 自定义行高 / 列宽
        self.row_heights: dict[int, int] = {}
        self.col_widths: dict[int, int] = {}

        # 全局数据库配置
        self.db_configs: dict[str, "DbConfig"] = {}

        # 模板元信息
        self.template_name: str = "未命名模板"
        self.template_description: str = ""

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    # ------------------------------------------------------------------
    # 获取有效样式（按优先级合并）
    # ------------------------------------------------------------------
    def get_effective_style(self, row: int, col: int) -> CellStyle:
        style = CellStyle().merge(self.default_style)
        if col in self.column_styles:
            style = style.merge(self.column_styles[col])
        if row in self.row_styles:
            style = style.merge(self.row_styles[row])
        if (row, col) in self.cell_styles:
            style = style.merge(self.cell_styles[(row, col)])
        return style

    # ------------------------------------------------------------------
    # 设置 / 清除样式
    # ------------------------------------------------------------------
    def set_column_style(self, col: int, style: CellStyle):
        self.column_styles[col] = style.clone()

    def set_row_style(self, row: int, style: CellStyle):
        self.row_styles[row] = style.clone()

    def set_cell_style(self, row: int, col: int, style: CellStyle):
        self.cell_styles[(row, col)] = style.clone()

    def clear_column_style(self, col: int):
        self.column_styles.pop(col, None)

    def clear_row_style(self, row: int):
        self.row_styles.pop(row, None)

    def clear_cell_style(self, row: int, col: int):
        self.cell_styles.pop((row, col), None)

    def clear_all(self):
        """清除所有非默认样式和数据。"""
        self.column_styles.clear()
        self.row_styles.clear()
        self.cell_styles.clear()
        self.merge_ranges.clear()
        self.cell_data.clear()
        self.row_heights.clear()
        self.col_widths.clear()
        self.template_name = "未命名模板"
        self.template_description = ""

    # ------------------------------------------------------------------
    # 查询某个维度是否有自定义样式
    # ------------------------------------------------------------------
    def get_scope_style(self, scope: StyleScope,
                        row: int = -1, col: int = -1) -> Optional[CellStyle]:
        if scope == StyleScope.DEFAULT:
            return self.default_style
        if scope == StyleScope.COLUMN and col >= 0:
            return self.column_styles.get(col)
        if scope == StyleScope.ROW and row >= 0:
            return self.row_styles.get(row)
        if scope == StyleScope.CELL and row >= 0 and col >= 0:
            return self.cell_styles.get((row, col))
        return None

    # ------------------------------------------------------------------
    # 合并单元格
    # ------------------------------------------------------------------
    def add_merge_range(self, top: int, bottom: int, left: int, right: int):
        """添加合并区域，自动移除与已有合并区域冲突的部分。"""
        # 移除被新范围完全包含的旧合并区域
        to_remove = set()
        for mr in self.merge_ranges:
            if (mr.top_row >= top and mr.bottom_row <= bottom and
                    mr.left_col >= left and mr.right_col <= right):
                to_remove.add(mr)
            # 移除与新范围有重叠的
            elif not (mr.bottom_row < top or mr.top_row > bottom or
                      mr.right_col < left or mr.left_col > right):
                to_remove.add(mr)
        self.merge_ranges -= to_remove
        self.merge_ranges.add(MergeRange(top, bottom, left, right))

    def remove_merge_range(self, row: int, col: int):
        """移除包含该单元格的合并区域。"""
        to_remove = set()
        for mr in self.merge_ranges:
            if mr.contains(row, col):
                to_remove.add(mr)
        self.merge_ranges -= to_remove

    def get_merge_range(self, row: int, col: int) -> Optional[MergeRange]:
        """获取包含该单元格的合并区域。"""
        for mr in self.merge_ranges:
            if mr.contains(row, col):
                return mr
        return None

    def is_merged_cell(self, row: int, col: int) -> bool:
        return self.get_merge_range(row, col) is not None

    def is_merge_master(self, row: int, col: int) -> bool:
        mr = self.get_merge_range(row, col)
        return mr is not None and mr.is_top_left(row, col)

    # ------------------------------------------------------------------
    # 单元格数据
    # ------------------------------------------------------------------
    def get_cell_data(self, row: int, col: int) -> CellData:
        return self.cell_data.get((row, col), CellData())

    def set_cell_data(self, row: int, col: int, data: CellData):
        self.cell_data[(row, col)] = data

    def clear_cell_data(self, row: int, col: int):
        self.cell_data.pop((row, col), None)

    # ------------------------------------------------------------------
    # 调整表格尺寸
    # ------------------------------------------------------------------
    def resize(self, rows: int, cols: int):
        self._rows = rows
        self._cols = cols
        # 清理越界样式
        self.column_styles = {c: s for c, s in self.column_styles.items() if c < cols}
        self.row_styles = {r: s for r, s in self.row_styles.items() if r < rows}
        self.cell_styles = {(r, c): s for (r, c), s in self.cell_styles.items()
                            if r < rows and c < cols}
        # 清理越界合并区域
        self.merge_ranges = {mr for mr in self.merge_ranges
                             if mr.bottom_row < rows and mr.right_col < cols}
        # 清理越界数据
        self.cell_data = {(r, c): d for (r, c), d in self.cell_data.items()
                          if r < rows and c < cols}
        self.row_heights = {r: h for r, h in self.row_heights.items() if r < rows}
        self.col_widths = {c: w for c, w in self.col_widths.items() if c < cols}

    def insert_row(self, row: int):
        """在指定行前插入一行。"""
        self._rows += 1
        # 更新行样式索引
        new_row_styles = {}
        for r, s in self.row_styles.items():
            new_row_styles[r if r < row else r + 1] = s
        self.row_styles = new_row_styles
        # 更新单元格样式索引
        new_cell_styles = {}
        for (r, c), s in self.cell_styles.items():
            new_cell_styles[(r if r < row else r + 1, c)] = s
        self.cell_styles = new_cell_styles
        # 更新合并区域
        new_merges = set()
        for mr in self.merge_ranges:
            new_merges.add(MergeRange(
                mr.top_row if mr.top_row < row else mr.top_row + 1,
                mr.bottom_row if mr.bottom_row < row else mr.bottom_row + 1,
                mr.left_col, mr.right_col,
            ))
        self.merge_ranges = new_merges
        # 更新数据
        new_data = {}
        for (r, c), d in self.cell_data.items():
            new_data[(r if r < row else r + 1, c)] = d
        self.cell_data = new_data
        # 更新行高
        new_heights = {}
        for r, h in self.row_heights.items():
            new_heights[r if r < row else r + 1] = h
        self.row_heights = new_heights

    def delete_row(self, row: int):
        """删除指定行。"""
        if self._rows <= 1:
            return
        self._rows -= 1
        new_row_styles = {}
        for r, s in self.row_styles.items():
            if r < row:
                new_row_styles[r] = s
            elif r > row:
                new_row_styles[r - 1] = s
        self.row_styles = new_row_styles

        new_cell_styles = {}
        for (r, c), s in self.cell_styles.items():
            if r < row:
                new_cell_styles[(r, c)] = s
            elif r > row:
                new_cell_styles[(r - 1, c)] = s
        self.cell_styles = new_cell_styles

        new_merges = set()
        for mr in self.merge_ranges:
            if mr.top_row == mr.bottom_row == row:
                continue  # 删除单行合并区域
            new_top = mr.top_row if mr.top_row < row else mr.top_row - 1
            new_bottom = mr.bottom_row if mr.bottom_row < row else mr.bottom_row - 1
            if new_top <= new_bottom:
                new_merges.add(MergeRange(new_top, new_bottom, mr.left_col, mr.right_col))
        self.merge_ranges = new_merges

        new_data = {}
        for (r, c), d in self.cell_data.items():
            if r < row:
                new_data[(r, c)] = d
            elif r > row:
                new_data[(r - 1, c)] = d
        self.cell_data = new_data

        new_heights = {}
        for r, h in self.row_heights.items():
            if r < row:
                new_heights[r] = h
            elif r > row:
                new_heights[r - 1] = h
        self.row_heights = new_heights

    def insert_column(self, col: int):
        """在指定列前插入一列。"""
        self._cols += 1
        new_col_styles = {}
        for c, s in self.column_styles.items():
            new_col_styles[c if c < col else c + 1] = s
        self.column_styles = new_col_styles

        new_cell_styles = {}
        for (r, c), s in self.cell_styles.items():
            new_cell_styles[(r, c if c < col else c + 1)] = s
        self.cell_styles = new_cell_styles

        new_merges = set()
        for mr in self.merge_ranges:
            new_merges.add(MergeRange(
                mr.top_row, mr.bottom_row,
                mr.left_col if mr.left_col < col else mr.left_col + 1,
                mr.right_col if mr.right_col < col else mr.right_col + 1,
            ))
        self.merge_ranges = new_merges

        new_data = {}
        for (r, c), d in self.cell_data.items():
            new_data[(r, c if c < col else c + 1)] = d
        self.cell_data = new_data

        new_widths = {}
        for c, w in self.col_widths.items():
            new_widths[c if c < col else c + 1] = w
        self.col_widths = new_widths

    def delete_column(self, col: int):
        """删除指定列。"""
        if self._cols <= 1:
            return
        self._cols -= 1
        new_col_styles = {}
        for c, s in self.column_styles.items():
            if c < col:
                new_col_styles[c] = s
            elif c > col:
                new_col_styles[c - 1] = s
        self.column_styles = new_col_styles

        new_cell_styles = {}
        for (r, c), s in self.cell_styles.items():
            if c < col:
                new_cell_styles[(r, c)] = s
            elif c > col:
                new_cell_styles[(r, c - 1)] = s
        self.cell_styles = new_cell_styles

        new_merges = set()
        for mr in self.merge_ranges:
            if mr.left_col == mr.right_col == col:
                continue
            new_left = mr.left_col if mr.left_col < col else mr.left_col - 1
            new_right = mr.right_col if mr.right_col < col else mr.right_col - 1
            if new_left <= new_right:
                new_merges.add(MergeRange(mr.top_row, mr.bottom_row, new_left, new_right))
        self.merge_ranges = new_merges

        new_data = {}
        for (r, c), d in self.cell_data.items():
            if c < col:
                new_data[(r, c)] = d
            elif c > col:
                new_data[(r, c - 1)] = d
        self.cell_data = new_data

        new_widths = {}
        for c, w in self.col_widths.items():
            if c < col:
                new_widths[c] = w
            elif c > col:
                new_widths[c - 1] = w
        self.col_widths = new_widths

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "meta": {
                "template_name": self.template_name,
                "template_description": self.template_description,
                "rows": self._rows,
                "cols": self._cols,
            },
            "default_style": self.default_style.to_dict(),
            "column_styles": {
                str(c): s.to_dict() for c, s in self.column_styles.items()
            },
            "row_styles": {
                str(r): s.to_dict() for r, s in self.row_styles.items()
            },
            "cell_styles": {
                f"{r},{c}": s.to_dict() for (r, c), s in self.cell_styles.items()
            },
            "merge_ranges": [
                mr.to_dict() for mr in self.merge_ranges
            ],
            "cell_data": {
                f"{r},{c}": d.to_dict() for (r, c), d in self.cell_data.items()
            },
            "row_heights": {str(r): h for r, h in self.row_heights.items()},
            "col_widths": {str(c): w for c, w in self.col_widths.items()},
            "db_configs": {
                k: v.to_dict() for k, v in self.db_configs.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateModel":
        from .db_config import DbConfig
        meta = data.get("meta", {})
        model = cls(rows=meta.get("rows", 30), cols=meta.get("cols", 10))
        model.template_name = meta.get("template_name", "未命名模板")
        model.template_description = meta.get("template_description", "")

        # 默认样式
        if "default_style" in data:
            model.default_style = CellStyle.from_dict(data["default_style"])

        # 列样式
        for k, v in data.get("column_styles", {}).items():
            model.column_styles[int(k)] = CellStyle.from_dict(v)

        # 行样式
        for k, v in data.get("row_styles", {}).items():
            model.row_styles[int(k)] = CellStyle.from_dict(v)

        # 单元格样式
        for k, v in data.get("cell_styles", {}).items():
            r, c = k.split(",")
            model.cell_styles[(int(r), int(c))] = CellStyle.from_dict(v)

        # 合并区域
        for mr_data in data.get("merge_ranges", []):
            model.merge_ranges.add(MergeRange.from_dict(mr_data))

        # 单元格数据
        for k, v in data.get("cell_data", {}).items():
            r, c = k.split(",")
            model.cell_data[(int(r), int(c))] = CellData.from_dict(v)

        # 行高/列宽
        for k, v in data.get("row_heights", {}).items():
            model.row_heights[int(k)] = v
        for k, v in data.get("col_widths", {}).items():
            model.col_widths[int(k)] = v

        # 数据库配置
        for k, v in data.get("db_configs", {}).items():
            model.db_configs[k] = DbConfig.from_dict(v)

        return model
