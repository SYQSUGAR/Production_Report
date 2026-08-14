"""Database connection, query execution, and schema inspection."""

from typing import Optional

from models.db_config import DbConfig


class DbHandler:
    def __init__(self):
        self._connections: dict[str, object] = {}

    def connect(self, config: DbConfig, config_key: str = "default") -> bool:
        try:
            if config.db_type == "mysql":
                import pymysql
                conn = pymysql.connect(
                    host=config.host, port=config.port, user=config.user,
                    password=config.password, database=config.database,
                    charset=config.charset, cursorclass=pymysql.cursors.DictCursor,
                )
            elif config.db_type == "sqlserver":
                import pyodbc
                conn = pyodbc.connect(
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={config.host},{config.port};DATABASE={config.database};"
                    f"UID={config.user};PWD={config.password};"
                )
            else:
                print(f"不支持的数据库类型: {config.db_type}")
                return False
            self._connections[config_key] = conn
            return True
        except Exception as exc:
            print(f"数据库连接失败[{config_key}]: {exc}")
            return False

    def disconnect(self, config_key: str = "default"):
        conn = self._connections.pop(config_key, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def disconnect_all(self):
        for key in list(self._connections):
            self.disconnect(key)

    def execute_query(self, sql: str, config_key: str = "default") -> Optional[str]:
        conn = self._connections.get(config_key)
        if not conn:
            return None
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                value = list(row.values())[0] if isinstance(row, dict) else row[0]
                return str(value) if value is not None else ""
            return ""
        except Exception as exc:
            print(f"查询执行失败: {exc}")
            return None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_schema_metadata(self, config_key: str = "default") -> dict[str, list[str]]:
        """Return ``{table_name: [column_name, ...]}`` for the connection."""
        conn = self._connections.get(config_key)
        if not conn:
            return {}
        cursor = None
        try:
            cursor = conn.cursor()
            if "pymysql" in type(conn).__module__.lower():
                cursor.execute(
                    "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION"
                )
            else:
                cursor.execute(
                    "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_CATALOG = DB_NAME() "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
                )
            metadata: dict[str, list[str]] = {}
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    table = str(row.get("TABLE_NAME") or row.get("table_name") or "")
                    column = str(row.get("COLUMN_NAME") or row.get("column_name") or "")
                elif len(row) >= 3:
                    schema, raw_table, column = row[0], row[1], row[2]
                    table = (f"{schema}.{raw_table}" if schema and
                             str(schema).lower() != "dbo" else str(raw_table))
                    column = str(column)
                else:
                    table, column = str(row[0]), str(row[1])
                if table and column:
                    metadata.setdefault(table, []).append(column)
            return metadata
        except Exception as exc:
            print(f"数据库结构读取失败[{config_key}]: {exc}")
            return {}
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def is_connected(self, config_key: str = "default") -> bool:
        return config_key in self._connections
