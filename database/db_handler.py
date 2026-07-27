"""通用数据库处理器 —— 支持 MySQL / SQLServer 查询接口。"""

from typing import Optional
from models.db_config import DbConfig


class DbHandler:
    """数据库查询处理器，预留 MySQL 和 SQLServer 两套连接方式。"""

    def __init__(self):
        self._connections: dict[str, object] = {}

    def connect(self, config: DbConfig, config_key: str = "default") -> bool:
        """建立数据库连接。"""
        try:
            if config.db_type == "mysql":
                import pymysql
                conn = pymysql.connect(
                    host=config.host,
                    port=config.port,
                    user=config.user,
                    password=config.password,
                    database=config.database,
                    charset=config.charset,
                    cursorclass=pymysql.cursors.DictCursor,
                )
                self._connections[config_key] = conn
                return True
            elif config.db_type == "sqlserver":
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={config.host},{config.port};"
                    f"DATABASE={config.database};"
                    f"UID={config.user};"
                    f"PWD={config.password};"
                )
                conn = pyodbc.connect(conn_str)
                self._connections[config_key] = conn
                return True
            else:
                print(f"不支持的数据库类型: {config.db_type}")
                return False
        except Exception as e:
            print(f"数据库连接失败 [{config_key}]: {e}")
            return False

    def disconnect(self, config_key: str = "default"):
        """断开指定数据库连接。"""
        conn = self._connections.pop(config_key, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def disconnect_all(self):
        for key in list(self._connections.keys()):
            self.disconnect(key)

    def execute_query(self, sql: str, config_key: str = "default") -> Optional[str]:
        """执行查询并返回第一个结果的值（字符串形式）。"""
        conn = self._connections.get(config_key)
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            if row:
                if isinstance(row, dict):
                    val = list(row.values())[0]
                else:
                    val = row[0]
                return str(val) if val is not None else ""
            return ""
        except Exception as e:
            print(f"查询执行失败: {e}")
            return None

    def is_connected(self, config_key: str = "default") -> bool:
        return config_key in self._connections
