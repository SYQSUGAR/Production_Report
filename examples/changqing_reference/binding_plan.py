"""长庆油田生产运行日报单元格数据库绑定方案。

这是模板案例配置，不被主程序自动导入。
它只设置 TemplateModel 单元格的 QueryBinding；SQL 仍由程序现有查询构建器根据
表名、字段、筛选条件、集计方式和时间规则动态生成，没有在程序代码中写死 SQL。

需要把本方案应用到用户本机已有的“长庆油田”自定义预设时，请先导出/提供该预设 JSON。
"""

from models.db_config import QueryBinding
from models.template_model import CellData


def _qb(table, field, aggregate, filters, time_field, range_type):
    return QueryBinding.from_dict({
        "enabled": True,
        "query_type": "aggregate",
        "db_config_key": "default",
        "table_name": table,
        "field_name": field,
        "aggregate_func": aggregate,
        "sql_mode": "builder",
        "custom_sql": "",
        "sync_modes": False,
        "joins": [],
        "filters": [
            {
                "connector": "where" if i == 0 else "and",
                "field": key,
                "op": "=",
                "value": value,
            }
            for i, (key, value) in enumerate(filters)
        ],
        "date_placeholder": "",
        "time_binding": {
            "enabled": True,
            "time_field": time_field,
            "range_type": range_type,
            "mode": "selected",
            "fixed_start": "",
            "fixed_end": "",
        },
    })


def _cell(address):
    letters = ""
    digits = ""
    for ch in address.upper():
        if ch.isalpha():
            letters += ch
        elif ch.isdigit():
            digits += ch
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return int(digits) - 1, col - 1


def build_binding_plan():
    plan = {}

    def put(address, binding):
        plan[address] = binding

    def utility(cells, location, metric_code):
        for address, period in zip(cells, ("day", "month", "year")):
            put(address, _qb(
                "cq_hourly_metric", "metric_value", "SUM",
                [("location_name", location), ("metric_code", metric_code)],
                "record_time", period,
            ))

    def maintenance(cells, location, category):
        for address, period in zip(cells, ("day", "month", "year")):
            put(address, _qb(
                "cq_maintenance_event", "event_id", "COUNT",
                [("location_name", location), ("category", category)],
                "event_time", period,
            ))

    def runtime(cells, team, equipment):
        for address, period in zip(cells, ("day", "month", "year")):
            put(address, _qb(
                "cq_equipment_hourly", "runtime_hours", "SUM",
                [("team_name", team), ("equipment_name", equipment)],
                "record_time", period,
            ))

    def equipment_sensor(address, team, equipment, field):
        put(address, _qb(
            "cq_equipment_hourly", field, "AVG",
            [("team_name", team), ("equipment_name", equipment)],
            "record_time", "day",
        ))

    def temperature(address, location, temperature_type):
        put(address, _qb(
            "cq_temperature_hourly", "temperature_c", "AVG",
            [("location_name", location), ("temperature_type", temperature_type)],
            "record_time", "day",
        ))

    utility(("A6", "B6", "C6"), "兴隆园小区", "water_supply")
    utility(("D6", "E6", "F6"), "兴隆园小区", "electricity_supply")
    utility(("G6", "H6", "I6"), "兴隆园小区", "industrial_gas")
    maintenance(("J6", "K6", "L6"), "兴隆园小区", "水维修（公建）")
    maintenance(("M6", "N6", "O6"), "兴隆园小区", "电维修（公建）")
    maintenance(("P6", "Q6", "R6"), "兴隆园小区", "维修服务")

    utility(("A10", "B10", "C10"), "长庆综合科研楼", "water_use")
    utility(("D10", "E10", "F10"), "长庆综合科研楼", "electricity_use")
    utility(("G10", "H10", "I10"), "长庆大厦", "water_use")
    utility(("J10", "K10", "L10"), "长庆大厦", "electricity_use")
    utility(("M10", "N10", "O10"), "苏里格大厦", "water_use")
    utility(("P10", "Q10", "R10"), "苏里格大厦", "electricity_use")

    utility(("A14", "B14", "C14"), "长庆科技大厦", "water_use")
    utility(("D14", "E14", "F14"), "长庆科技大厦", "electricity_use")
    utility(("G14", "H14", "I14"), "明光路办公区", "water_use")
    utility(("J14", "K14", "L14"), "明光路办公区", "electricity_use")
    utility(("M14", "O14", "Q14"), "长实大厦", "electricity_supply")

    for row, equipment in ((17, "1#锅炉"), (18, "2#锅炉"), (19, "3#锅炉"), (20, "4#锅炉")):
        equipment_sensor(f"D{row}", "锅炉运行班", equipment, "pressure_mpa")
        equipment_sensor(f"F{row}", "锅炉运行班", equipment, "supply_temp_c")
        equipment_sensor(f"H{row}", "锅炉运行班", equipment, "return_temp_c")
        runtime((f"J{row}", f"L{row}", f"N{row}"), "锅炉运行班", equipment)

    utility(("B23", "C23", "D23"), "换热站", "electricity_use")
    utility(("E23", "F23", "G23"), "锅炉房", "electricity_use")
    utility(("H23", "I23", "J23"), "锅炉房", "gas_use")
    utility(("K23", "L23", "M23"), "锅炉房", "hot_water_use")
    utility(("N23", "O23", "P23"), "锅炉房", "makeup_water")

    for address, location, kind in (
        ("B26", "一区、三区热水", "出水温度"), ("D26", "一区、三区热水", "回水温度"),
        ("F26", "二区热水", "出水温度"), ("H26", "二区热水", "回水温度"),
        ("J26", "新三区热水", "出水温度"), ("L26", "新三区热水", "回水温度"),
        ("N26", "五区热水", "出水温度"), ("P26", "五区热水", "回水温度"),
        ("R26", "分水", "温度"),
        ("B29", "增压站二区", "出水温度"), ("C29", "增压站三区", "出水温度"),
        ("D29", "增压站五区", "出水温度"),
    ):
        temperature(address, location, kind)

    utility(("E29", "F29", "G29"), "增压站二区", "electricity_use")
    utility(("H29", "I29", "J29"), "增压站三区", "electricity_use")
    utility(("K29", "L29", "M29"), "增压站五区", "electricity_use")

    cooling_units = {
        "科研楼制冷班": ((32, "1#机组"), (33, "2#机组"), (34, "3#机组")),
        "大厦制冷班": ((35, "1#机组"), (36, "2#机组")),
        "明光路制冷班": (
            (37, "1#机组"), (38, "2#机组"), (39, "3#机组"), (40, "4#机组"),
            (41, "5#机组"), (42, "6#机组"), (43, "7#机组"), (44, "8#机组"),
            (45, "9#机组"), (46, "10#机组"), (47, "11#机组"),
        ),
        "苏里格制冷班": ((48, "1#机组"), (49, "2#机组")),
    }
    for team, units in cooling_units.items():
        for row, equipment in units:
            equipment_sensor(f"C{row}", team, equipment, "supply_temp_c")
            equipment_sensor(f"D{row}", team, equipment, "return_temp_c")
            runtime((f"E{row}", f"F{row}", f"G{row}"), team, equipment)

    for row, team in (
        (32, "科研楼制冷班"),
        (35, "大厦制冷班"),
        (37, "明光路制冷班"),
        (48, "苏里格制冷班"),
    ):
        utility((f"H{row}", f"I{row}", f"J{row}"), team, "water_use")
        utility((f"K{row}", f"L{row}", f"M{row}"), team, "electricity_use")
        utility((f"N{row}", f"O{row}", f"P{row}"), team, "gas_use")

    return plan


def apply_binding_plan(template):
    """只修改数据库绑定，不动模板原有文字、样式、合并、行高和列宽。"""
    for address, binding in build_binding_plan().items():
        row, col = _cell(address)
        old = template.get_cell_data(row, col)
        template.set_cell_data(
            row, col,
            CellData(static_text=old.static_text, query_binding=binding, note=old.note),
        )
    return template


def main():
    import argparse
    from export.template_io import TemplateIO

    parser = argparse.ArgumentParser(description="把长庆油田参考数据库绑定应用到模板 JSON")
    parser.add_argument("input_json", help="原长庆油田模板/预设 JSON")
    parser.add_argument("output_json", help="输出 JSON；建议先输出到新文件核对")
    args = parser.parse_args()

    template = TemplateIO.load(args.input_json)
    apply_binding_plan(template)
    TemplateIO.save(template, args.output_json)
    print(f"已写入 {len(build_binding_plan())} 个单元格数据库绑定：{args.output_json}")


if __name__ == "__main__":
    main()
