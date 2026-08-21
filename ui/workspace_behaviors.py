"""Workspace 级文件行为：预设保存/替换 + 未保存模板保护。"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QLabel, QPushButton, QMessageBox, QWidget, QSplitter,
    QAbstractItemView,
)

from export.template_io import TemplateIO
from models.template_model import TemplateModel
from templates.presets import (
    BUILTIN_TEMPLATES, get_custom_presets, load_template_by_name,
    save_as_custom_preset,
)
from ui.preview_table import PreviewTable


class PresetSaveDialog(QDialog):
    """通过“预设名称”唯一决定新建还是覆盖，并提供已有预设预览。"""

    def __init__(self, template: TemplateModel, parent=None):
        super().__init__(parent)
        self._source_template = template
        self._result_name = ""
        self.setWindowTitle("保存为预设模板")
        self.resize(980, 620)
        self._build_ui()
        self._reload_presets()

    @property
    def saved_name(self) -> str:
        return self._result_name

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        split = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("已有预设模板"))
        self._list = QListWidget()
        self._list.setMinimumWidth(230)
        self._list.currentItemChanged.connect(self._on_selected)
        ll.addWidget(self._list, 1)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self._preview_title = QLabel("预设内容预览")
        self._preview_title.setStyleSheet("font-weight:bold;")
        rl.addWidget(self._preview_title)
        self._preview_model = TemplateModel(rows=1, cols=1)
        self._preview = PreviewTable(self._preview_model, is_admin=False)
        self._preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        rl.addWidget(self._preview, 1)
        split.addWidget(right)
        split.setSizes([250, 700])
        root.addWidget(split, 1)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("预设名称:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("请输入预设名称")
        name_row.addWidget(self._name, 1)
        self._save_btn = QPushButton("保存预设")
        self._save_btn.clicked.connect(self._save_by_name)
        name_row.addWidget(self._save_btn)
        root.addLayout(name_row)

        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch(1)
        cancel_row.addWidget(cancel)
        root.addLayout(cancel_row)

    def _reload_presets(self):
        self._list.clear()
        custom = get_custom_presets()

        # 同名自定义预设视为对内置预设的覆盖，只显示一项，避免名称重复。
        for name in BUILTIN_TEMPLATES:
            if name in custom:
                continue
            item = QListWidgetItem(f"[内置] {name}")
            item.setData(Qt.ItemDataRole.UserRole, (name, "builtin"))
            self._list.addItem(item)

        for name in custom:
            label = "[自定义·覆盖内置]" if name in BUILTIN_TEMPLATES else "[自定义]"
            item = QListWidgetItem(f"{label} {name}")
            item.setData(Qt.ItemDataRole.UserRole, (name, "custom"))
            self._list.addItem(item)

    def _on_selected(self, current, _previous):
        if current is None:
            return
        name, kind = current.data(Qt.ItemDataRole.UserRole)

        # 点击已有预设只做两件事：把名字填入输入框，并预览该预设。
        # 最终是否覆盖完全由“预设名称”输入框 + 保存按钮决定。
        self._name.setText(name)
        self._name.selectAll()
        try:
            if kind == "builtin":
                model = BUILTIN_TEMPLATES[name]()
                label = "内置预设"
            else:
                model = load_template_by_name(name)
                label = "自定义预设"
            self._preview_model = TemplateModel.from_dict(model.to_dict())
            self._preview.set_template(self._preview_model)
            self._preview.set_query_results({})
            self._preview_title.setText(f"{name} — {label}")
        except Exception as exc:
            self._preview_title.setText(f"无法预览：{exc}")

    def _confirm_replace(self, name: str) -> bool:
        reply = QMessageBox.question(
            self,
            "覆盖预设模板",
            f"预设模板“{name}”已经存在。\n\n是否用当前模板覆盖它？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _write(self, name: str):
        # 即使名称原来属于内置模板，也写入自定义预设目录；加载时自定义优先，
        # 因而实现“覆盖”。删除该自定义预设后，原内置模板会自然恢复。
        save_as_custom_preset(self._source_template, name)
        self._result_name = name
        self.accept()

    def _save_by_name(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.information(self, "请输入名称", "请输入预设名称。")
            self._name.setFocus()
            return

        custom = get_custom_presets()
        exists = name in custom or name in BUILTIN_TEMPLATES
        if exists and not self._confirm_replace(name):
            return
        self._write(name)


class WorkspaceFileBehavior:
    """把 MainWindow 的文件动作升级为工作区级、带未保存保护的行为。"""

    _DESTRUCTIVE_TEXTS = (
        "新建模板", "打开模板", "导入 Excel", "恢复默认模板",
    )

    def __init__(self, workspace, editor):
        self.workspace = workspace
        self.editor = editor
        self._baseline = self._snapshot()
        self._install()

    def _snapshot(self):
        return self.editor._template.to_dict()

    def mark_clean(self):
        self._baseline = self._snapshot()

    def is_dirty(self) -> bool:
        return self._snapshot() != self._baseline

    @staticmethod
    def _clean_text(text: str) -> str:
        return text.replace("&", "").replace("...", "").strip()

    def _file_menu(self):
        for action in self.editor.menuBar().actions():
            menu = action.menu()
            if menu and self._clean_text(menu.title()).startswith("文件"):
                return menu
        return None

    def _iter_actions(self, menu):
        for action in menu.actions():
            if action.menu() is not None:
                yield from self._iter_actions(action.menu())
            elif not action.isSeparator():
                yield action

    def _find_action(self, startswith: str):
        menu = self._file_menu()
        if menu is None:
            return None
        for action in self._iter_actions(menu):
            if self._clean_text(action.text()).startswith(startswith):
                return action
        return None

    @staticmethod
    def _replace_trigger(action, callback):
        if action is None:
            return
        try:
            action.triggered.disconnect()
        except TypeError:
            pass
        action.triggered.connect(callback)

    def _install(self):
        self._replace_trigger(self._find_action("保存模板"), self._save)
        self._replace_trigger(self._find_action("另存模板"), self._save_as)
        self._replace_trigger(self._find_action("将当前模板保存为预设"), self._save_preset)

        self._replace_trigger(self._find_action("新建模板"), self._new)
        self._replace_trigger(self._find_action("打开模板"), self._open)
        self._replace_trigger(self._find_action("导入 Excel"), self._import_excel)
        self._replace_trigger(self._find_action("恢复默认模板"), self._restore_default)

        self.rebuild_guarded_preset_menu()

    def rebuild_guarded_preset_menu(self):
        menu = self.editor._preset_menu
        menu.clear()
        custom = get_custom_presets()

        for name in BUILTIN_TEMPLATES:
            if name in custom:
                continue
            action = menu.addAction(f"[内置] {name}")
            action.triggered.connect(lambda _checked=False, n=name: self._load_preset(n))

        if custom:
            menu.addSeparator()
            for name in custom:
                label = "[自定义·覆盖内置]" if name in BUILTIN_TEMPLATES else "[自定义]"
                action = menu.addAction(f"{label} {name}")
                action.triggered.connect(lambda _checked=False, n=name: self._load_preset(n))

    def _saved_file_matches_current(self) -> bool:
        path = self.editor._current_filepath
        if not path or not os.path.exists(path):
            return False
        try:
            return TemplateIO.load(path).to_dict() == self.editor._template.to_dict()
        except Exception:
            return False

    def confirm_replace_current(self) -> bool:
        if not self.is_dirty():
            return True
        box = QMessageBox(self.workspace)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("当前模板尚未保存")
        box.setText("当前模板已经修改，但尚未保存。")
        box.setInformativeText("在打开其他模板之前，是否保存当前修改？")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Discard:
            return True
        self.editor._save_template()
        if self._saved_file_matches_current():
            self.mark_clean()
            return True
        return False

    def _after_replaced(self):
        self.mark_clean()
        self.workspace._refresh_after_global_action()

    def _save(self, *_args):
        self.editor._save_template()
        if self._saved_file_matches_current():
            self.mark_clean()

    def _save_as(self, *_args):
        self.editor._save_as_template()
        if self._saved_file_matches_current():
            self.mark_clean()

    def _save_preset(self, *_args):
        dlg = PresetSaveDialog(self.editor._template, self.workspace)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.rebuild_guarded_preset_menu()
            self.editor._status_label.setText(f"已保存预设: {dlg.saved_name}")
            QMessageBox.information(
                self.workspace, "保存成功", f"模板已保存为预设“{dlg.saved_name}”。"
            )

    def _new(self, *_args):
        if not self.confirm_replace_current():
            return
        before = self.editor._template
        self.editor._new_template()
        if self.editor._template is not before:
            self._after_replaced()

    def _open(self, *_args):
        if not self.confirm_replace_current():
            return
        before = self.editor._template
        self.editor._load_template()
        if self.editor._template is not before:
            self._after_replaced()

    def _import_excel(self, *_args):
        if not self.confirm_replace_current():
            return
        before = self.editor._template
        self.editor._import_excel()
        if self.editor._template is not before:
            self._after_replaced()

    def _restore_default(self, *_args):
        if not self.confirm_replace_current():
            return
        before = self.editor._template
        self.editor._restore_default_template()
        if self.editor._template is not before:
            # 默认模板和预设一样，不对应用户打开的本地 JSON 源文件。
            # 因此恢复默认模板后 Ctrl+S 应进入“另存为 JSON”，不能覆盖之前的本地文件。
            self.editor._current_filepath = ""
            self._after_replaced()

    def _load_preset(self, name: str):
        if not self.confirm_replace_current():
            return
        try:
            template = load_template_by_name(name)
            self.editor._apply_loaded_template(template, name)
            self.editor._current_filepath = ""
            self._after_replaced()
        except Exception as exc:
            QMessageBox.critical(
                self.workspace, "加载失败", f"无法加载模板“{name}”:\n{exc}"
            )
