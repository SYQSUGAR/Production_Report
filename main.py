"""生产报表模板编辑与预览 —— 入口文件。"""

import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QLibraryInfo, QLocale, QTranslator
from PyQt6.QtGui import QFont

from ui.workspace_window import WorkspaceWindow
from ui.db_connection_patch import install_db_connection_patch


_APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".report_editor")
_CRASH_LOG = os.path.join(_APP_DATA_DIR, "crash.log")


def _write_crash_log(exc_type, exc_value, exc_tb):
    os.makedirs(_APP_DATA_DIR, exist_ok=True)
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open(_CRASH_LOG, "a", encoding="utf-8") as fp:
        fp.write("\n" + "=" * 80 + "\n")
        fp.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        fp.write(text)
    return text


def _exception_hook(exc_type, exc_value, exc_tb):
    """Qt 信号槽中未捕获异常也要记录，不再只表现为闪退。"""
    text = _write_crash_log(exc_type, exc_value, exc_tb)
    print(text, file=sys.stderr)
    app = QApplication.instance()
    if app is not None:
        try:
            QMessageBox.critical(
                None,
                "程序发生错误",
                f"程序发生未处理异常。\n\n{exc_value}\n\n详细信息已写入：\n{_CRASH_LOG}",
            )
        except Exception:
            pass


def _install_chinese_qt_translation(app: QApplication):
    """统一把 Qt 自带按钮/系统对话框切换为中文。

    这样 QMessageBox 的 Save/Discard/Cancel/Yes/No/OK 等标准按钮不会再
    因操作系统或 Qt 默认语言而显示英文。翻译文件缺失时应用仍可正常启动。
    """
    QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

    translators = []
    for base_name in ("qtbase_zh_CN", "qt_zh_CN"):
        translator = QTranslator(app)
        if translator.load(base_name, translations_path):
            app.installTranslator(translator)
            translators.append(translator)

    # QTranslator 必须保持引用，否则会被回收而失效。
    app._qt_zh_translators = translators


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("生产报表模板编辑与预览")
    _install_chinese_qt_translation(app)
    sys.excepthook = _exception_hook

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "宋体"])
    font.setPointSize(10)
    app.setFont(font)

    try:
        install_db_connection_patch()
        window = WorkspaceWindow()
        window.show()
        return app.exec()
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        _exception_hook(exc_type, exc_value, exc_tb)
        return 1


if __name__ == "__main__":
    sys.exit(main())
