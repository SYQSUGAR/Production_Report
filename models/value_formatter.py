"""按模板数字格式规范化数据库查询结果。"""

from datetime import date, datetime
import re


_NUMERIC_FORMATS = {"integer", "decimal_2", "decimal_3", "percent"}
_DATE_TOKENS = ("yyyy", "yy", "mm", "dd")


def _to_number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        raise ValueError("empty")
    return float(text)


def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        raise ValueError("empty")
    candidates = [
        text,
        text.replace("/", "-"),
    ]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(text)


def _excel_date_to_strftime(fmt: str) -> str:
    # 当前界面只开放这些日期 token，按展示用途做直接转换即可。
    return (fmt.replace("yyyy", "%Y")
               .replace("yy", "%y")
               .replace("mm", "%m")
               .replace("dd", "%d"))


def _custom_numeric_decimals(fmt: str) -> int | None:
    if not fmt or not any(ch in fmt for ch in "0#"):
        return None
    if "." not in fmt:
        return 0
    tail = fmt.split(".", 1)[1]
    digits = [ch for ch in tail if ch in "0#"]
    return len(digits)


def format_display_value(value, number_format: str | None) -> str:
    """把数据库结果转换为模板中应显示的文本。

    这只影响界面展示，不改变模板中的原始查询定义。
    """
    if value is None:
        return ""

    fmt = (number_format or "general").strip()
    if fmt in ("", "general", "text"):
        return str(value)

    try:
        if fmt == "integer":
            return f"{_to_number(value):,.0f}"
        if fmt == "decimal_2":
            return f"{_to_number(value):,.2f}"
        if fmt == "decimal_3":
            return f"{_to_number(value):,.3f}"
        if fmt == "percent":
            return f"{_to_number(value) * 100:.2f}%"
        if fmt.endswith("%") and "0" in fmt:
            decimals = max(0, len(fmt.split(".", 1)[1].split("%", 1)[0])) if "." in fmt else 0
            return f"{_to_number(value) * 100:.{decimals}f}%"

        lowered = fmt.lower()
        if any(token in lowered for token in _DATE_TOKENS):
            dt = _to_datetime(value)
            return dt.strftime(_excel_date_to_strftime(lowered))

        decimals = _custom_numeric_decimals(fmt)
        if decimals is not None:
            number = _to_number(value)
            use_grouping = "," in fmt
            body = f"{number:,.{decimals}f}" if use_grouping else f"{number:.{decimals}f}"
            prefix_match = re.match(r"^([^0#.,]+)", fmt)
            suffix_match = re.search(r"([^0#.,]+)$", fmt)
            prefix = prefix_match.group(1) if prefix_match else ""
            suffix = suffix_match.group(1) if suffix_match else ""
            return f"{prefix}{body}{suffix}"
    except (TypeError, ValueError, OverflowError):
        return str(value)

    return str(value)


def coerce_excel_value(value, number_format: str | None):
    """把值转换为适合 openpyxl + number_format 的底层类型。"""
    if value is None:
        return ""
    fmt = (number_format or "general").strip()
    if fmt == "text":
        return str(value)
    try:
        if fmt == "integer":
            return int(round(_to_number(value)))
        if fmt in ("decimal_2", "decimal_3", "percent"):
            return float(_to_number(value))
        if fmt.endswith("%") and "0" in fmt:
            return float(_to_number(value))
        if any(token in fmt.lower() for token in _DATE_TOKENS):
            return _to_datetime(value)
        if _custom_numeric_decimals(fmt) is not None:
            return float(_to_number(value))
    except (TypeError, ValueError, OverflowError):
        return str(value)
    return value
