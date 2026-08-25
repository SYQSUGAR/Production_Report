"""数据库配置与查询绑定模型。"""

import re
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from .time_binding import TimeBinding, TimeRangeType


class QueryType(Enum):
    SINGLE = "single"
    AGGREGATE = "aggregate"


SQL_OPERATOR_LABELS = {
    "=": "等于", ">": "大于", "<": "小于", "<=": "不大于", ">=": "不小于",
    "LIKE": "包含", "NOT LIKE": "不包含",
}
SQL_OPERATORS = list(SQL_OPERATOR_LABELS.keys())


@dataclass
class DbConfig:
    db_type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    user: str = ""
    password: str = ""
    # 仅为旧模板兼容保留。新版连接配置按服务器级保存，不要求数据库名。
    database: str = ""
    charset: str = "utf8mb4"

    def to_dict(self) -> dict:
        return {
            "db_type": self.db_type, "host": self.host, "port": self.port,
            "user": self.user, "password": self.password, "database": self.database,
            "charset": self.charset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DbConfig":
        return cls(
            db_type=data.get("db_type", "mysql"), host=data.get("host", "localhost"),
            port=data.get("port", 3306), user=data.get("user", ""),
            password=data.get("password", ""), database=data.get("database", ""),
            charset=data.get("charset", "utf8mb4"),
        )


@dataclass
class QueryBinding:
    """单元格数据库查询绑定。

    新版绑定会同时保存 database/schema/table 身份；只启用一个数据库时
    SQL 可以使用简写表名，多数据库时自动使用 database.table 消除歧义。
    """
    enabled: bool = False
    query_type: QueryType = QueryType.SINGLE
    db_config_key: str = ""
    database_name: str = ""
    schema_name: str = ""
    qualify_database: bool = False
    table_name: str = ""
    field_name: str = ""
    aggregate_func: str = ""
    sql_mode: str = "builder"
    custom_sql: str = ""
    sync_modes: bool = False
    joins: list[dict] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)
    date_placeholder: str = ""
    time_binding: TimeBinding = field(default_factory=TimeBinding)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled, "query_type": self.query_type.value,
            "db_config_key": self.db_config_key,
            "database_name": self.database_name,
            "schema_name": self.schema_name,
            "qualify_database": self.qualify_database,
            "table_name": self.table_name,
            "field_name": self.field_name, "aggregate_func": self.aggregate_func,
            "sql_mode": self.sql_mode, "custom_sql": self.custom_sql,
            "sync_modes": self.sync_modes, "joins": self.joins, "filters": self.filters,
            "date_placeholder": self.date_placeholder,
            "time_binding": self.time_binding.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueryBinding":
        return cls(
            enabled=data.get("enabled", False),
            query_type=QueryType(data.get("query_type", "single")),
            db_config_key=data.get("db_config_key", ""),
            database_name=data.get("database_name", ""),
            schema_name=data.get("schema_name", ""),
            qualify_database=data.get("qualify_database", False),
            table_name=data.get("table_name", ""),
            field_name=data.get("field_name", ""), aggregate_func=data.get("aggregate_func", ""),
            sql_mode=data.get("sql_mode", "builder"), custom_sql=data.get("custom_sql", ""),
            sync_modes=data.get("sync_modes", False), joins=data.get("joins", []),
            filters=data.get("filters", []), date_placeholder=data.get("date_placeholder", ""),
            time_binding=TimeBinding.from_dict(data.get("time_binding")),
        )

    @staticmethod
    def _format_value(op: str, val) -> str:
        s = str(val).strip()
        if op in ("LIKE", "NOT LIKE"):
            if not (s.startswith("%") or s.endswith("%")):
                s = f"%{s}%"
            return "'" + s.replace("'", "''") + "'"
        if s == "":
            return "''"
        if s in ("{start_time}", "{end_time}"):
            return s
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

    def _time_tokens(self, time_range=None) -> tuple[str, str] | None:
        if not self.time_binding.enabled:
            return None
        if time_range:
            start, end = time_range
            return self._format_datetime(start), self._format_datetime(end)
        if self.time_binding.range_type != TimeRangeType.FIXED:
            return "{start_time}", "{end_time}"
        try:
            start = datetime.fromisoformat(self.time_binding.fixed_start)
            end = datetime.fromisoformat(self.time_binding.fixed_end)
        except (TypeError, ValueError):
            return "{start_time}", "{end_time}"
        return self._format_datetime(start), self._format_datetime(end)

    def table_sql_name(self) -> str:
        table = self.table_name.strip()
        if not table:
            return ""
        # 用户手动输入了限定名时保持原样。
        if "." in table:
            return table
        if self.schema_name.strip():
            if self.database_name.strip() and self.qualify_database:
                return f"{self.database_name.strip()}.{self.schema_name.strip()}.{table}"
            return f"{self.schema_name.strip()}.{table}"
        if self.database_name.strip() and self.qualify_database:
            return f"{self.database_name.strip()}.{table}"
        return table

    def build_sql(self, date_value: str = "", time_range=None) -> str:
        if not self.enabled:
            return ""

        time_tokens = self._time_tokens(time_range)

        if self.sql_mode == "manual":
            sql = self.custom_sql.strip()
            if date_value:
                sql = sql.replace("{date}", date_value)
            if time_tokens:
                start_token, end_token = time_tokens
                if time_range or self.time_binding.range_type == TimeRangeType.FIXED:
                    sql = sql.replace("{start_time}", start_token)
                    sql = sql.replace("{end_time}", end_token)
            return sql

        table_expr = self.table_sql_name()
        if not table_expr or not self.field_name:
            return ""

        field_expr = self.field_name
        if self.query_type == QueryType.AGGREGATE and self.aggregate_func:
            field_expr = f"{self.aggregate_func}({self.field_name})"

        sql = f"SELECT {field_expr} FROM {table_expr}"
        for join in self.joins:
            join_table = (join.get("table") or "").strip()
            if join_table and join.get("on"):
                sql += f" {join.get('type', 'LEFT JOIN').upper()} {join_table} ON {join['on']}"

        conditions: list[tuple[str, str]] = []
        for f in self.filters:
            field_name = f.get("field", "")
            op = f.get("op", "=")
            val = f.get("value", "")
            if not field_name:
                continue
            if isinstance(val, str) and "{date}" in val and date_value:
                val = val.replace("{date}", date_value)
            conditions.append((
                f.get("connector", "AND").upper(),
                f"{field_name} {op} {self._format_value(op, val)}",
            ))

        if time_tokens and self.time_binding.time_field.strip():
            start_token, end_token = time_tokens
            tf = self.time_binding.time_field.strip()
            conditions.append(("AND", f"{tf} >= {start_token}"))
            conditions.append(("AND", f"{tf} < {end_token}"))

        if conditions:
            rendered = []
            for index, (connector, cond) in enumerate(conditions):
                prefix = "WHERE" if index == 0 else (connector if connector in ("AND", "OR") else "AND")
                rendered.append(f"{prefix} {cond}")
            sql += " " + " ".join(rendered)
        return sql

    def validate_time_sql(self) -> str:
        tb = self.time_binding
        if not tb.enabled:
            return ""
        if not tb.time_field.strip():
            return "时间绑定已启用，但未设置时间字段"
        if self.sql_mode != "manual":
            return ""
        sql = self.custom_sql or ""
        if "{start_time}" not in sql or "{end_time}" not in sql:
            return "手动 SQL 启用了时间绑定，必须同时包含 {start_time} 和 {end_time}"
        return ""


def _has_unsupported_clause(sql: str) -> bool:
    return bool(re.search(r"\b(JOIN|DISTINCT|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT)\b", sql, re.I))


def parse_condition(cond: str) -> dict | None:
    cond = cond.strip()
    for op in ("NOT LIKE", "LIKE", "<=", ">=", "=", ">", "<"):
        m = re.match(rf"^(.+?)\s+{re.escape(op)}\s+(.+)$", cond, re.IGNORECASE)
        if m:
            field_name = m.group(1).strip()
            value = m.group(2).strip().strip("'\"")
            if op in ("LIKE", "NOT LIKE"):
                value = value.strip("%")
            return {"field": field_name, "op": op, "value": value}
    return None


def parse_sql_to_binding(sql: str) -> dict:
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
    where_m = re.search(
        r"\bWHERE\b(.+?)(?=\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
        sql, re.I | re.S,
    )
    if not where_m:
        result["safe"] = not _has_unsupported_clause(sql)
        return result
    tokens = re.split(r"\s+(AND|OR)\s+", where_m.group(1).strip(), flags=re.IGNORECASE)
    filters = []
    connector = "where"
    for tok in tokens:
        if tok.upper() in ("AND", "OR"):
            connector = tok.lower()
            continue
        parsed = parse_condition(tok)
        if parsed:
            parsed["connector"] = connector
            filters.append(parsed)
            connector = "and"
    result["filters"] = filters
    result["safe"] = not _has_unsupported_clause(sql)
    return result
