"""数据库连接配置体验修正。

只处理数据库配置窗口的回显、立即持久化和连接错误提示；
不改变模板编辑、查询绑定或报表逻辑。
"""


def install_db_connection_patch():
    import ui.main_window as mw

    if getattr(mw, "_db_connection_patch_installed", False):
        return
    mw._db_connection_patch_installed = True

    # 1) 配置窗口打开时回显当前模板中已经保存的 default 配置。
    original_dialog_init = mw._DbConfigDialog.__init__

    def dialog_init(self, parent=None):
        original_dialog_init(self, parent)
        template = getattr(parent, "_template", None)
        config = template.db_configs.get("default") if template is not None else None
        if config is None:
            return

        idx = self._cmb_type.findText(config.db_type)
        if idx >= 0:
            self._cmb_type.setCurrentIndex(idx)
        self._txt_host.setText(config.host)
        self._spn_port.setValue(int(config.port))
        self._txt_user.setText(config.user)
        self._txt_password.setText(config.password)
        self._txt_database.setText(config.database)
        self._txt_charset.setText(config.charset)

    mw._DbConfigDialog.__init__ = dialog_init

    # 2) 重新连接同一个 config_key 前先关闭旧连接，并保留真实错误文本。
    def connect(self, config, config_key="default"):
        self.last_error = ""
        self.disconnect(config_key)
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
            elif config.db_type == "sqlserver":
                import pyodbc
                conn = pyodbc.connect(
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={config.host},{config.port};DATABASE={config.database};"
                    f"UID={config.user};PWD={config.password};"
                )
            else:
                self.last_error = f"不支持的数据库类型: {config.db_type}"
                print(self.last_error)
                return False

            self._connections[config_key] = conn
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"数据库连接失败[{config_key}]: {exc}")
            return False

    mw.DbHandler.connect = connect

    # 3) 点击“确定”后立即写入 last_session，而不是只等程序退出时保存。
    def db_config(self):
        dlg = mw._DbConfigDialog(self)
        if dlg.exec() == mw.QDialog.DialogCode.Accepted:
            config = dlg.get_config()
            self._db_handler.disconnect("default")
            self._template.db_configs["default"] = config
            self._save_session()
            self._status_label.setText("数据库配置已保存")

    mw.MainWindow._db_config = db_config

    # 4) 测试失败时直接显示 PyMySQL/ODBC 返回的具体错误。
    def db_test_connect(self):
        config = self._template.db_configs.get("default")
        if not config:
            mw.QMessageBox.warning(self, "提示", "请先在数据库菜单中配置连接信息")
            return

        success = self._db_handler.connect(config, "default")
        if success:
            mw.QMessageBox.information(self, "连接成功", "数据库连接测试通过")
        else:
            detail = getattr(self._db_handler, "last_error", "") or "未知错误"
            mw.QMessageBox.critical(
                self,
                "连接失败",
                f"数据库连接测试失败，请检查配置。\n\n详细错误：\n{detail}",
            )

    mw.MainWindow._db_test_connect = db_test_connect
