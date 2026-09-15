"""一次报表实例的时间上下文与时间解析逻辑。"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import calendar

from .time_binding import TimeBinding, TimeRangeType, TimeMode


def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _next_month_start(d: date) -> datetime:
    if d.month == 12:
        return datetime(d.year + 1, 1, 1)
    return datetime(d.year, d.month + 1, 1)


@dataclass
class ReportContext:
    """预览页为本次报表提供的运行参数。"""

    generated_at: datetime = field(default_factory=datetime.now)
    selected_day: date = field(default_factory=date.today)
    selected_month_year: int = field(default_factory=lambda: date.today().year)
    selected_month: int = field(default_factory=lambda: date.today().month)
    selected_year: int = field(default_factory=lambda: date.today().year)
    custom_start: datetime = field(default_factory=lambda: datetime.combine(date.today(), time.min))
    custom_end: datetime = field(default_factory=datetime.now)

    def resolve(self, binding: TimeBinding) -> tuple[datetime, datetime] | None:
        """把模板时间规则解析成统一的 [start, end) 区间。"""
        if not binding or not binding.enabled:
            return None

        kind = binding.range_type
        mode = binding.mode

        if kind == TimeRangeType.DAY:
            if mode == TimeMode.CURRENT:
                return _start_of_day(self.generated_at.date()), self.generated_at
            start = _start_of_day(self.selected_day)
            return start, start + timedelta(days=1)

        if kind == TimeRangeType.MONTH:
            if mode == TimeMode.CURRENT:
                start = datetime(self.generated_at.year, self.generated_at.month, 1)
                return start, self.generated_at
            start = datetime(self.selected_month_year, self.selected_month, 1)
            return start, _next_month_start(start.date())

        if kind == TimeRangeType.YEAR:
            if mode == TimeMode.CURRENT:
                return datetime(self.generated_at.year, 1, 1), self.generated_at
            return datetime(self.selected_year, 1, 1), datetime(self.selected_year + 1, 1, 1)

        if kind == TimeRangeType.CUSTOM:
            if self.custom_end <= self.custom_start:
                return None
            return self.custom_start, self.custom_end

        if kind == TimeRangeType.FIXED:
            try:
                start = datetime.fromisoformat(binding.fixed_start)
                end = datetime.fromisoformat(binding.fixed_end)
            except (TypeError, ValueError):
                return None
            if end <= start:
                return None
            return start, end

        return None

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(sep=" "),
            "selected_day": self.selected_day.isoformat(),
            "selected_month_year": self.selected_month_year,
            "selected_month": self.selected_month,
            "selected_year": self.selected_year,
            "custom_start": self.custom_start.isoformat(sep=" "),
            "custom_end": self.custom_end.isoformat(sep=" "),
        }
