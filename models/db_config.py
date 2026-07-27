"""数据库配置与查询绑定模型。"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class QueryType(Enum):
    SINGLE = "single"      # 单值查询
    AGGREGATE = "aggregate"  # 聚合查询（SUM/COUNT/AVG/MAX/MIN）


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
    """单元格的数据库查询绑定信息。"""
    enabled: bool = False               # 是否启用数据库绑定
    query_type: QueryType = QueryType.SINGLE  # 查询类型
    db_config_key: str = ""             # 使用的数据库配置标识
    table_name: str = ""                # 数据表名
    field_name: str = ""                # 查询字段名
    aggregate_func: str = ""            # 聚合函数: SUM/COUNT/AVG/MAX/MIN
    filters: list[dict] = field(default_factory=list)  # 多条件筛选 [{"field":"", "op":"=", "value":""}]
    date_placeholder: str = ""          # 日期占位符，如 "{date}"，运行时替换为选定日期

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "query_type": self.query_type.value,
            "db_config_key": self.db_config_key,
            "table_name": self.table_name,
            "field_name": self.field_name,
            "aggregate_func": self.aggregate_func,
            "filters": self.filters,
            "date_placeholder": self.date_placeholder,
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
            filters=data.get("filters", []),
            date_placeholder=data.get("date_placeholder", ""),
        )

    def build_sql(self, date_value: str = "") -> str:
        """根据配置构建 SQL 查询语句。"""
        if not self.enabled or not self.table_name or not self.field_name:
            return ""

        field_expr = self.field_name
        if self.query_type == QueryType.AGGREGATE and self.aggregate_func:
            field_expr = f"{self.aggregate_func}({self.field_name})"

        sql = f"SELECT {field_expr} FROM {self.table_name}"

        conditions = []
        for f in self.filters:
            val = f.get("value", "")
            # 日期占位符替换
            if isinstance(val, str) and "{date}" in val and date_value:
                val = val.replace("{date}", date_value)
            conditions.append(f"{f['field']} {f['op']} {val}")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return sql
