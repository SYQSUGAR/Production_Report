"""生产报表模板编辑与预览 —— 入口文件。"""

import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.workspace_window import WorkspaceWindow


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


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("生产报表模板编辑与预览")
    sys.excepthook = _exception_hook

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "宋体"])
    font.setPointSize(10)
    app.setFont(font)

    try:
        window = WorkspaceWindow()
        window.show()
        return app.exec()
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        _exception_hook(exc_type, exc_value, exc_tb)
        return 1


if __name__ == "__main__":
    sys.exit(main())
