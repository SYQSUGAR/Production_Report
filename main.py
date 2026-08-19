"""生产报表模板编辑与预览 —— 入口文件。"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.workspace_window import WorkspaceWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("生产报表模板编辑与预览")

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "宋体"])
    font.setPointSize(10)
    app.setFont(font)

    window = WorkspaceWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
