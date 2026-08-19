"""报表单元格时间绑定模型。

模板只保存“时间规则”，具体运行日期由报表预览的 ReportContext 提供。
所有规则最终统一解析为 [start_time, end_time) 半开区间。
"""

from dataclasses import dataclass
from enum import Enum


class TimeRangeType(Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"
    FIXED = "fixed"


class TimeMode(Enum):
    CURRENT = "current"      # 当日 / 当月 / 当年
    SELECTED = "selected"    # 预览界面指定日 / 月 / 年


@dataclass
class TimeBinding:
    enabled: bool = False
    time_field: str = ""
    range_type: TimeRangeType = TimeRangeType.DAY
    mode: TimeMode = TimeMode.SELECTED
    fixed_start: str = ""
    fixed_end: str = ""

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "time_field": self.time_field,
            "range_type": self.range_type.value,
            "mode": self.mode.value,
            "fixed_start": self.fixed_start,
            "fixed_end": self.fixed_end,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "TimeBinding":
        data = data or {}
        try:
            range_type = TimeRangeType(data.get("range_type", "day"))
        except ValueError:
            range_type = TimeRangeType.DAY
        try:
            mode = TimeMode(data.get("mode", "selected"))
        except ValueError:
            mode = TimeMode.SELECTED
        return cls(
            enabled=bool(data.get("enabled", False)),
            time_field=data.get("time_field", ""),
            range_type=range_type,
            mode=mode,
            fixed_start=data.get("fixed_start", ""),
            fixed_end=data.get("fixed_end", ""),
        )
