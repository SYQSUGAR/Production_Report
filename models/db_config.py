"""数据库配置与查询绑定模型。"""

import re
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from .time_binding import TimeBinding


class QueryType(Enum):
    SINGLE = "single"      # 单值查询
    AGGREGATE = "aggregate"  # 聚合查询（SUM/COUNT/AVG/MAX/MIN）


# 运算符映射：SQL 运算符 -> 中文显示
SQL_OPERATOR_LABELS = {
    "=": "等于",
    ">": "大于",
    "<": "小于",
    "<=": "不大于",
    ">=": "不小于",
    "LIKE": "包含",
    "NOT LIKE": "不包含",
}
SQL_OPERATORS = list(SQL_OPERATOR_LABELS.keys())


@dataclass
class DbConfig:
    """数据库连接配置，预留给 MySQL / SQLServer 通用查询接口。"""
    db_type: str = "mysql"          # "mysql" | "sqlserver"
    host: str = "localhost"
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"

    def to_dict(self) -> dict:
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DbConfig":
        return cls(
            db_type=data.get("db_type", "mysql"),
            host=data.get("host", "localhost"),
            port=data.get("port", 3306),
            user=data.get("user", ""),
            password=data.get("password", ""),
            database=data.get("database", ""),
            charset=data.get("charset", "utf8mb4"),
        )


@dataclass
class QueryBinding:
    """单元格的数据库查询绑定信息。

    支持两种编写模式：
      - builder：可视化条件构建（字段 + 运算符 + 值 + and/or 连接）
      - manual：手动输入完整 SQL 语句

    时间条件不再只依赖 ``{date}``。新增 ``time_binding`` 保存模板级时间规则，
    运行时由报表预览把规则解析为 ``start_time`` / ``end_time`` 后传入 build_sql。
    """
    enabled: bool = False
    query_type: QueryType = QueryType.SINGLE
    db_config_key: str = ""
    table_name: str = ""
    field_name: str = ""
    aggregate_func: str = ""
    sql_mode: str = "builder"
    custom_sql: str = ""
    sync_modes: bool = False
    joins: list[dict] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)
    date_placeholder: str = ""          # 兼容旧模板
    time_binding: TimeBinding = field(default_factory=TimeBinding)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "query_type": self.query_type.value,
            "db_config_key": self.db_config_key,
            "table_name": self.table_name,
            "field_name": self.field_name,
            "aggregate_func": self.aggregate_func,
            "sql_mode": self.sql_mode,
            "custom_sql": self.custom_sql,
            "sync_modes": self.sync_modes,
            "joins": self.joins,
            "filters": self.filters,
            "date_placeholder": self.date_placeholder,
            "time_binding": self.time_binding.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueryBinding":
        return cls(
            enabled=data.get("enabled", False),
            query_type=QueryType(data.get("query_type", "single")),
            db_config_key=data.get("db_config_key", ""),
            table_name=data.get("table_name", ""),
            field_name=data.get("field_name", ""),
            aggregate_func=data.get("aggregate_func", ""),
            sql_mode=data.get("sql_mode", "builder"),
            custom_sql=data.get("custom_sql", ""),
            sync_modes=data.get("sync_modes", False),
            joins=data.get("joins", []),
            filters=data.get("filters", []),
            date_placeholder=data.get("date_placeholder", ""),
            time_binding=TimeBinding.from_dict(data.get("time_binding")),
        )

    @staticmethod
    def _format_value(op: str, val) -> str:
        """格式化条件值：字符串加引号，数值不加；包含/不包含自动包裹 %。"""
        s = str(val).strip()
        if op in ("LIKE", "NOT LIKE"):
            if not (s.startswith("%") or s.endswith("%")):
                s = f"%{s}%"
            return "'" + s.replace("'", "''") + "'"
        if s == "":
            return "''"
        try:
            float(s)
            return s
        except ValueError:
            return "'" + s.replace("'", "''") + "'"

    @staticmethod
    def _format_datetime(value: datetime | str) -> str:
        if isinstance(value, datetime):
            text = value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            text = str(value)
        return "'" + text.replace("'", "''") + "'"

    def build_sql(self, date_value: str = "", time_range=None) -> str:
        """生成 SQL。

        ``time_range`` 为 ``(start_datetime, end_datetime)``。builder 模式会依据
        ``time_binding.time_field`` 自动追加半开区间条件；manual 模式只替换
        ``{start_time}`` / ``{end_time}`` 占位符，避免擅自改写复杂手写 SQL。
        """
        if not self.enabled:
            return ""

        if self.sql_mode == "manual":
            sql = self.custom_sql.strip()
            if date_value:
                sql = sql.replace("{date}", date_value)
            if time_range:
                start, end = time_range
                sql = sql.replace("{start_time}", self._format_datetime(start))
                sql = sql.replace("{end_time}", self._format_datetime(end))
            return sql

        if not self.table_name or not self.field_name:
            return ""

        field_expr = self.field_name
        if self.query_type == QueryType.AGGREGATE and self.aggregate_func:
            field_expr = f"{self.aggregate_func}({self.field_name})"

        sql = f"SELECT {field_expr} FROM {self.table_name}"
        for join in self.joins:
            if join.get("table") and join.get("on"):
                sql += f" {join.get('type', 'LEFT JOIN').upper()} {join['table']} ON {join['on']}"

        conditions: list[tuple[str, str]] = []
        for f in self.filters:
            field_name = f.get("field", "")
            op = f.get("op", "=")
            val = f.get("value", "")
            if not field_name:
                continue
            if isinstance(val, str) and "{date}" in val and date_value:
                val = val.replace("{date}", date_value)
            cond = f"{field_name} {op} {self._format_value(op, val)}"
            connector = f.get("connector", "AND").upper()
            conditions.append((connector, cond))

        if time_range and self.time_binding.enabled and self.time_binding.time_field.strip():
            start, end = time_range
            tf = self.time_binding.time_field.strip()
            conditions.append(("AND", f"{tf} >= {self._format_datetime(start)}"))
            conditions.append(("AND", f"{tf} < {self._format_datetime(end)}"))

        if conditions:
            rendered = []
            for index, (connector, cond) in enumerate(conditions):
                rendered.append(("WHERE" if index == 0 else (connector if connector in ("AND", "OR") else "AND")) + " " + cond)
            sql += " " + " ".join(rendered)
        return sql


def _has_unsupported_clause(sql: str) -> bool:
    """检测条件构建器无法无损表达的子句（JOIN/去重/分组/排序/限制等）。"""
    return bool(re.search(
        r"\b(JOIN|DISTINCT|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT)\b",
        sql, re.I,
    ))


def parse_condition(cond: str) -> dict | None:
    """解析单个条件 `field op value`。"""
    cond = cond.strip()
    for op in ("NOT LIKE", "LIKE", "<=", ">=", "=", ">", "<"):
        m = re.match(rf"^(.+?)\s+{re.escape(op)}\s+(.+)$", cond, re.IGNORECASE)
        if m:
            field_name = m.group(1).strip()
            value = m.group(2).strip()
            value = value.strip("'\"")
            if op in ("LIKE", "NOT LIKE"):
                value = value.strip("%")
            return {"field": field_name, "op": op, "value": value}
    return None


def parse_sql_to_binding(sql: str) -> dict:
    """把简单 SELECT ... FROM ... WHERE ... 语句解析为绑定配置。"""
    result = {"field": "", "table": "", "aggregate": "", "filters": [], "safe": False}
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return result

    m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\S+)", sql, re.IGNORECASE)
    if not m:
        return result
    if re.search(r"\b(UNION|WITH|INTERSECT|EXCEPT)\b|\(\s*SELECT\b", sql, re.I):
        return result
    field_expr = m.group(1).strip()
    result["table"] = m.group(2)

    agg_m = re.match(r"(\w+)\((\w+)\)", field_expr)
    if agg_m:
        result["aggregate"] = agg_m.group(1).upper()
        result["field"] = agg_m.group(2)
    else:
        result["field"] = field_expr

    where_m = re.search(r"\bWHERE\b(.+?)(?=\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|$)", sql, re.I | re.S)
    if not where_m:
        result["safe"] = not _has_unsupported_clause(sql)
        return result
    where_clause = where_m.group(1).strip()

    tokens = re.split(r"\s+(AND|OR)\s+", where_clause, flags=re.IGNORECASE)
    filters = []
    connector = "where"
    for tok in tokens:
        if tok.upper() in ("AND", "OR"):
            connector = tok.lower()
            continue
        cond = parse_condition(tok)
        if cond:
            cond["connector"] = connector
            filters.append(cond)
            connector = "and"
    result["filters"] = filters
    result["safe"] = not _has_unsupported_clause(sql)
    return result
