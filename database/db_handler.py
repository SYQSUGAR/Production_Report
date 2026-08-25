"""Database connection, query execution, and multi-database schema inspection."""

from typing import Optional

from models.db_config import DbConfig


class DbHandler:
    SYSTEM_MYSQL_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}
    SYSTEM_SQLSERVER_DATABASES = {"master", "model", "msdb", "tempdb"}

    def __init__(self):
        self._connections: dict[str, object] = {}
        self._configs: dict[str, DbConfig] = {}
        self.last_error: str = ""

    def connect(self, config: DbConfig, config_key: str = "default") -> bool:
        """Connect to the database server.

        ``config.database`` is optional and retained only for backward
        compatibility with older templates. New projects connect at server
        level first, then choose one or more databases separately.
        """
        self.last_error = ""
        self.disconnect(config_key)
        try:
            if config.db_type == "mysql":
                import pymysql

                kwargs = dict(
                    host=config.host,
                    port=int(config.port),
                    user=config.user,
                    password=config.password,
                    charset=config.charset or "utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                if (config.database or "").strip():
                    kwargs["database"] = config.database.strip()
                conn = pymysql.connect(**kwargs)
            elif config.db_type == "sqlserver":
                import pyodbc

                parts = [
                    "DRIVER={ODBC Driver 17 for SQL Server}",
                    f"SERVER={config.host},{int(config.port)}",
                    f"UID={config.user}",
                    f"PWD={config.password}",
                ]
                if (config.database or "").strip():
                    parts.append(f"DATABASE={config.database.strip()}")
                conn = pyodbc.connect(";".join(parts) + ";")
            else:
                self.last_error = f"不支持的数据库类型: {config.db_type}"
                return False

            self._connections[config_key] = conn
            self._configs[config_key] = config
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"数据库连接失败[{config_key}]: {exc}")
            return False

    def disconnect(self, config_key: str = "default"):
        conn = self._connections.pop(config_key, None)
        self._configs.pop(config_key, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def disconnect_all(self):
        for key in list(self._connections):
            self.disconnect(key)

    def is_connected(self, config_key: str = "default") -> bool:
        return config_key in self._connections

    def list_databases(self, config_key: str = "default", include_system: bool = False) -> list[str]:
        """Return databases/catalogs visible to the connected account."""
        conn = self._connections.get(config_key)
        config = self._configs.get(config_key)
        if not conn or not config:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            if config.db_type == "mysql":
                cursor.execute("SHOW DATABASES")
                names = []
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        name = next(iter(row.values()), "")
                    else:
                        name = row[0]
                    name = str(name)
                    if name and (include_system or name.lower() not in self.SYSTEM_MYSQL_DATABASES):
                        names.append(name)
            else:
                cursor.execute("SELECT name FROM sys.databases WHERE state = 0 ORDER BY name")
                names = []
                for row in cursor.fetchall():
                    name = str(row[0])
                    if name and (include_system or name.lower() not in self.SYSTEM_SQLSERVER_DATABASES):
                        names.append(name)
            return sorted(set(names), key=str.lower)
        except Exception as exc:
            self.last_error = str(exc)
            print(f"数据库列表读取失败[{config_key}]: {exc}")
            return []
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_multi_schema_metadata(
        self,
        databases: list[str],
        config_key: str = "default",
    ) -> dict[str, dict[str, list[str]]]:
        """Return ``{database: {table: [column, ...]}}`` for selected databases."""
        conn = self._connections.get(config_key)
        config = self._configs.get(config_key)
        selected = [str(name).strip() for name in databases if str(name).strip()]
        if not conn or not config or not selected:
            return {}

        result: dict[str, dict[str, list[str]]] = {name: {} for name in selected}
        cursor = None
        try:
            cursor = conn.cursor()
            if config.db_type == "mysql":
                placeholders = ",".join(["%s"] * len(selected))
                cursor.execute(
                    "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    f"WHERE TABLE_SCHEMA IN ({placeholders}) "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION",
                    selected,
                )
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        database = str(row.get("TABLE_SCHEMA") or row.get("table_schema") or "")
                        table = str(row.get("TABLE_NAME") or row.get("table_name") or "")
                        column = str(row.get("COLUMN_NAME") or row.get("column_name") or "")
                    else:
                        database, table, column = map(str, row[:3])
                    if database in result and table and column:
                        result[database].setdefault(table, []).append(column)
            else:
                for database in selected:
                    safe_db = database.replace("]", "]]" )
                    cursor.execute(
                        f"SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME "
                        f"FROM [{safe_db}].INFORMATION_SCHEMA.COLUMNS "
                        "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
                    )
                    for row in cursor.fetchall():
                        schema, raw_table, column = map(str, row[:3])
                        table = f"{schema}.{raw_table}" if schema else raw_table
                        result[database].setdefault(table, []).append(column)
            return result
        except Exception as exc:
            self.last_error = str(exc)
            print(f"数据库结构读取失败[{config_key}]: {exc}")
            return {}
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_schema_metadata(self, config_key: str = "default") -> dict[str, list[str]]:
        """Backward-compatible metadata for the connection's current database."""
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
                    table = f"{schema}.{raw_table}" if schema and str(schema).lower() != "dbo" else str(raw_table)
                    column = str(column)
                else:
                    table, column = str(row[0]), str(row[1])
                if table and column:
                    metadata.setdefault(table, []).append(column)
            return metadata
        except Exception as exc:
            self.last_error = str(exc)
            print(f"数据库结构读取失败[{config_key}]: {exc}")
            return {}
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def _select_database(self, config_key: str, database_name: str):
        if not database_name:
            return
        conn = self._connections.get(config_key)
        config = self._configs.get(config_key)
        if not conn or not config:
            return
        if config.db_type == "mysql":
            conn.select_db(database_name)
        else:
            safe_db = database_name.replace("]", "]]" )
            cursor = conn.cursor()
            try:
                cursor.execute(f"USE [{safe_db}]")
            finally:
                cursor.close()

    def execute_query(
        self,
        sql: str,
        config_key: str = "default",
        database_name: str = "",
    ) -> Optional[str]:
        conn = self._connections.get(config_key)
        if not conn:
            return None
        cursor = None
        try:
            self._select_database(config_key, database_name)
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                value = list(row.values())[0] if isinstance(row, dict) else row[0]
                return str(value) if value is not None else ""
            return ""
        except Exception as exc:
            self.last_error = str(exc)
            print(f"查询执行失败: {exc}")
            return None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def execute_rows(
        self,
        sql: str,
        config_key: str = "default",
        database_name: str = "",
    ) -> tuple[list[str], list[list[object]]] | None:
        """Execute a read-only SELECT and return column names plus rows.

        A tuple cursor is used for MySQL so duplicate column names from ``t1.*, t2.*``
        are not collapsed by DictCursor. This method is intended for preview windows.
        """
        conn = self._connections.get(config_key)
        config = self._configs.get(config_key)
        if not conn or not config:
            self.last_error = "数据库未连接"
            return None
        if not (sql or "").lstrip().upper().startswith("SELECT"):
            self.last_error = "数据预览仅支持 SELECT 查询"
            return None
        cursor = None
        try:
            self._select_database(config_key, database_name)
            if config.db_type == "mysql":
                import pymysql
                cursor = conn.cursor(pymysql.cursors.Cursor)
            else:
                cursor = conn.cursor()
            cursor.execute(sql)
            description = cursor.description or []
            columns = [str(item[0]) for item in description]
            rows = [list(row) for row in cursor.fetchall()]
            return columns, rows
        except Exception as exc:
            self.last_error = str(exc)
            print(f"预览查询执行失败: {exc}")
            return None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
