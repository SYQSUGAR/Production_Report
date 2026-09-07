"""内置生产日报预设模板 —— 供水、供电、维修类报表模板。

每个函数返回一个预配置好的 TemplateModel，可直接加载使用。
支持用户自定义预设模板（JSON 文件存储）。
"""

import os
import json
from models.template_model import (
    TemplateModel, CellStyle, MergeRange, CellData, NumberFormat,
)
from models.db_config import QueryBinding, QueryType
from PyQt6.QtCore import Qt

# 自定义预设存储目录
_CUSTOM_PRESETS_DIR = os.path.join(os.path.expanduser("~"), ".report_editor", "presets")
os.makedirs(_CUSTOM_PRESETS_DIR, exist_ok=True)


def get_custom_presets() -> dict[str, str]:
    """获取所有用户自定义预设：{名称: json文件路径}。"""
    presets = {}
    if os.path.isdir(_CUSTOM_PRESETS_DIR):
        for fname in sorted(os.listdir(_CUSTOM_PRESETS_DIR)):
            if fname.endswith(".json"):
                name = fname[:-5]  # 去掉 .json 后缀
                presets[name] = os.path.join(_CUSTOM_PRESETS_DIR, fname)
    return presets


def save_as_custom_preset(template: TemplateModel, name: str):
    """将模板保存为自定义预设。"""
    from export.template_io import TemplateIO
    filepath = os.path.join(_CUSTOM_PRESETS_DIR, f"{name}.json")
    TemplateIO.save(template, filepath)


def import_custom_preset(filepath: str) -> str:
    """从外部 JSON 文件导入为自定义预设，返回预设名称。"""
    from export.template_io import TemplateIO
    import shutil
    name = os.path.splitext(os.path.basename(filepath))[0]
    # 如果有重名则加序号
    base_name = name
    idx = 1
    while os.path.exists(os.path.join(_CUSTOM_PRESETS_DIR, f"{name}.json")):
        name = f"{base_name} ({idx})"
        idx += 1
    dest = os.path.join(_CUSTOM_PRESETS_DIR, f"{name}.json")
    shutil.copy2(filepath, dest)
    return name


def delete_custom_preset(name: str):
    """删除一个自定义预设。"""
    filepath = os.path.join(_CUSTOM_PRESETS_DIR, f"{name}.json")
    if os.path.exists(filepath):
        os.remove(filepath)


def load_template_by_name(name: str) -> TemplateModel:
    """根据名称加载模板；同名自定义预设优先，可覆盖内置预设。"""
    from export.template_io import TemplateIO
    custom = get_custom_presets()
    if name in custom:
        return TemplateIO.load(custom[name])
    if name in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[name]()
    raise ValueError(f"模板 '{name}' 不存在")


def water_supply_daily_report() -> TemplateModel:
    """供水生产运行日报模板。

    表格结构: 10 列 x 20 行
    列: 序号 | 水厂名称 | 设计供水能力(万m³/d) | 当日供水量(万m³) | 本月累计(万m³)
         | 供水压力(MPa) | 水质达标率(%) | 设备运行状态 | 值班人员 | 备注
    """
    tmpl = TemplateModel(rows=20, cols=10)
    tmpl.template_name = "供水生产运行日报"
    tmpl.template_description = "供水类生产运行日报标准模板"

    # 标题行
    tmpl.add_merge_range(0, 0, 0, 9)
    tmpl.set_cell_data(0, 0, CellData(static_text="供水生产运行日报"))

    # 标题样式
    title_style = CellStyle(font_size=16, bold=True,
                            alignment=int(Qt.AlignmentFlag.AlignCenter),
                            bg_color="#1F4E79", fg_color="#FFFFFF")
    tmpl.set_cell_style(0, 0, title_style)

    # 表头行
    headers = [
        "序号", "水厂名称", "设计供水能力\n(万m³/d)", "当日供水量\n(万m³)",
        "本月累计\n(万m³)", "供水压力\n(MPa)", "水质达标率\n(%)",
        "设备运行状态", "值班人员", "备注",
    ]
    header_style = CellStyle(font_size=10, bold=True,
                             alignment=int(Qt.AlignmentFlag.AlignCenter),
                             bg_color="#D6E4F0", fg_color="#1F4E79")
    for i, h in enumerate(headers):
        tmpl.set_cell_data(1, i, CellData(static_text=h))
        tmpl.set_cell_style(1, i, header_style)

    # 设置行高
    tmpl.row_heights[0] = 40
    tmpl.row_heights[1] = 50

    # 列宽
    col_widths = {0: 50, 1: 120, 2: 100, 3: 100, 4: 100,
                  5: 90, 6: 90, 7: 100, 8: 80, 9: 80}
    tmpl.col_widths = col_widths

    # 预设水厂名称 (第2-5行)
    stations = ["城东水厂", "城西水厂", "开发区水厂", "高新区水厂"]
    for i, name in enumerate(stations):
        tmpl.set_cell_data(2 + i, 0, CellData(static_text=str(i + 1)))
        tmpl.set_cell_data(2 + i, 1, CellData(static_text=name))

    # 合计行
    tmpl.set_cell_data(6, 0, CellData(static_text=""))
    tmpl.set_cell_data(6, 1, CellData(static_text="合计"))
    tmpl.add_merge_range(6, 6, 0, 1)

    # 数据库绑定示例 (当日供水量)
    for i in range(4):
        qb = QueryBinding(
            enabled=False,  # 默认关闭，管理员可手动开启
            query_type=QueryType.SINGLE,
            table_name="water_supply_data",
            field_name="daily_output",
            date_placeholder="{date}",
            filters=[
                {"field": "station_name", "op": "=", "value": f"'{stations[i]}'"},
                {"field": "record_date", "op": "=", "value": "'{date}'"},
            ],
        )
        cd = CellData(static_text="", query_binding=qb)
        tmpl.set_cell_data(2 + i, 3, cd)

    # 底部备注
    tmpl.add_merge_range(18, 18, 0, 9)
    tmpl.set_cell_data(18, 0, CellData(static_text="制表人: _______  审核人: _______  日期: _______"))
    tmpl.set_cell_style(18, 0, CellStyle(alignment=int(Qt.AlignmentFlag.AlignLeft), font_size=9))

    return tmpl


def electricity_daily_report() -> TemplateModel:
    """供电生产运行日报模板。

    表格结构: 10 列 x 20 行
    列: 序号 | 变电站名称 | 主变容量(MVA) | 当日最高负荷(MW) | 当日供电量(万kWh)
         | 本月累计(万kWh) | 负荷率(%) | 设备运行状态 | 值班人员 | 备注
    """
    tmpl = TemplateModel(rows=20, cols=10)
    tmpl.template_name = "供电生产运行日报"
    tmpl.template_description = "供电类生产运行日报标准模板"

    # 标题行
    tmpl.add_merge_range(0, 0, 0, 9)
    tmpl.set_cell_data(0, 0, CellData(static_text="供电生产运行日报"))

    title_style = CellStyle(font_size=16, bold=True,
                            alignment=int(Qt.AlignmentFlag.AlignCenter),
                            bg_color="#1A3A59", fg_color="#FFFFFF")
    tmpl.set_cell_style(0, 0, title_style)

    # 表头
    headers = [
        "序号", "变电站名称", "主变容量\n(MVA)", "当日最高负荷\n(MW)",
        "当日供电量\n(万kWh)", "本月累计\n(万kWh)", "负荷率\n(%)",
        "设备运行状态", "值班人员", "备注",
    ]
    header_style = CellStyle(font_size=10, bold=True,
                             alignment=int(Qt.AlignmentFlag.AlignCenter),
                             bg_color="#D9E8F7", fg_color="#1A3A59")
    for i, h in enumerate(headers):
        tmpl.set_cell_data(1, i, CellData(static_text=h))
        tmpl.set_cell_style(1, i, header_style)

    tmpl.row_heights[0] = 40
    tmpl.row_heights[1] = 50

    col_widths = {0: 50, 1: 120, 2: 90, 3: 100, 4: 100,
                  5: 100, 6: 80, 7: 100, 8: 80, 9: 80}
    tmpl.col_widths = col_widths

    # 预设变电站名称
    stations = ["110kV城中变", "110kV城东变", "220kV南郊变", "110kV北郊变", "35kV工业园变"]
    for i, name in enumerate(stations):
        tmpl.set_cell_data(2 + i, 0, CellData(static_text=str(i + 1)))
        tmpl.set_cell_data(2 + i, 1, CellData(static_text=name))

    # 合计行
    tmpl.add_merge_range(7, 7, 0, 1)
    tmpl.set_cell_data(7, 0, CellData(static_text=""))
    tmpl.set_cell_data(7, 1, CellData(static_text="合计"))

    # 底部备注
    tmpl.add_merge_range(18, 18, 0, 9)
    tmpl.set_cell_data(18, 0, CellData(static_text="制表人: _______  审核人: _______  日期: _______"))
    tmpl.set_cell_style(18, 0, CellStyle(alignment=int(Qt.AlignmentFlag.AlignLeft), font_size=9))

    return tmpl


def maintenance_daily_report() -> TemplateModel:
    """维修生产运行日报模板。

    表格结构: 10 列 x 20 行
    列: 序号 | 维修工单号 | 设备名称 | 故障类型 | 报修时间 | 完成时间
         | 维修人员 | 维修结果 | 材料费用(元) | 备注
    """
    tmpl = TemplateModel(rows=20, cols=10)
    tmpl.template_name = "维修生产运行日报"
    tmpl.template_description = "维修类生产运行日报标准模板"

    # 标题行
    tmpl.add_merge_range(0, 0, 0, 9)
    tmpl.set_cell_data(0, 0, CellData(static_text="维修生产运行日报"))

    title_style = CellStyle(font_size=16, bold=True,
                            alignment=int(Qt.AlignmentFlag.AlignCenter),
                            bg_color="#7B241C", fg_color="#FFFFFF")
    tmpl.set_cell_style(0, 0, title_style)

    # 表头
    headers = [
        "序号", "维修工单号", "设备名称", "故障类型", "报修时间",
        "完成时间", "维修人员", "维修结果", "材料费用(元)", "备注",
    ]
    header_style = CellStyle(font_size=10, bold=True,
                             alignment=int(Qt.AlignmentFlag.AlignCenter),
                             bg_color="#F5D5D5", fg_color="#7B241C")
    for i, h in enumerate(headers):
        tmpl.set_cell_data(1, i, CellData(static_text=h))
        tmpl.set_cell_style(1, i, header_style)

    tmpl.row_heights[0] = 40
    tmpl.row_heights[1] = 50

    col_widths = {0: 50, 1: 110, 2: 100, 3: 80, 4: 100,
                  5: 100, 6: 80, 7: 80, 8: 90, 9: 80}
    tmpl.col_widths = col_widths

    # 材料费用列使用两位小数格式
    for r in range(2, 18):
        tmpl.set_cell_style(r, 8, CellStyle(number_format=NumberFormat.DECIMAL_2.value))

    # 底部备注
    tmpl.add_merge_range(18, 18, 0, 9)
    tmpl.set_cell_data(18, 0, CellData(static_text="制表人: _______  审核人: _______  日期: _______"))
    tmpl.set_cell_style(18, 0, CellStyle(alignment=int(Qt.AlignmentFlag.AlignLeft), font_size=9))

    return tmpl


# 内置模板注册表
BUILTIN_TEMPLATES = {
    "供水生产运行日报": water_supply_daily_report,
    "供电生产运行日报": electricity_daily_report,
    "维修生产运行日报": maintenance_daily_report,
}
