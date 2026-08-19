"""模板编辑器的完整单元格撤销/恢复与复制粘贴增强。"""

from types import MethodType

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMessageBox

from models.template_model import CellData


def install_editor_history(editor, after_change=None):
    """给现有 MainWindow 增强完整单元格历史与剪贴板能力。

    现有 MainWindow 已经支持文字、样式、合并和结构撤销。本模块在不破坏
    现有逻辑的前提下补充：
      - CellData（静态文字 + 数据库绑定 + 时间绑定 + 备注）整体撤销/恢复；
      - 标准复制粘贴携带完整 CellData；
      - 多单元格粘贴仍作为一个 undo batch；
      - 撤销/恢复/粘贴后通知外部属性栏刷新。
    """
    if getattr(editor, "_complete_history_installed", False):
        return
    editor._complete_history_installed = True

    original_apply = editor._apply_undo_change

    def apply_undo_change(self, change: tuple, use_new: bool):
        kind = change[0]
        if kind == "cell_data":
            _, row, col, old_data, new_data = change
            payload = new_data if use_new else old_data
            cd = CellData.from_dict(payload)
            self._template.set_cell_data(row, col, cd)
            self._preview.refresh_cell(row, col)
            if (self._formula_bar._current_row == row and
                    self._formula_bar._current_col == col):
                self._formula_bar.set_current_cell(row, col, cd.static_text or "")
            return
        original_apply(change, use_new)

    editor._apply_undo_change = MethodType(apply_undo_change, editor)

    # ------------------------------------------------------------------
    # 复制：在原“文字 + 样式”剪贴板基础上追加完整 CellData。
    # ------------------------------------------------------------------
    def upgrade_internal_clipboard(*_args):
        clipboard = editor._clipboard
        if not clipboard or not clipboard.get("cells"):
            return
        cells = editor._preview.get_selected_cells_raw()
        if not cells:
            return
        min_r = min(r for r, _ in cells)
        min_c = min(c for _, c in cells)
        for (dr, dc), payload in list(clipboard["cells"].items()):
            if not isinstance(payload, tuple) or len(payload) >= 3:
                continue
            row, col = min_r + dr, min_c + dc
            text, style = payload
            cd = editor._template.get_cell_data(row, col)
            clipboard["cells"][(dr, dc)] = (text, style, cd.to_dict())

    # ------------------------------------------------------------------
    # 粘贴：普通粘贴复制完整 CellData；仅粘贴内容仍只写静态文字；
    # 格式粘贴仍只写样式。所有目标单元格合并为一个 undo batch。
    # ------------------------------------------------------------------
    def paste_from_clipboard(self, clipboard: dict, paste_text: bool, paste_style: bool):
        mapping = self._paste_mapping(clipboard)
        if mapping is None:
            QMessageBox.warning(
                self, "无法粘贴",
                "复制区域与粘贴区域的大小不同，且目标区域不是源区域的整数倍。",
            )
            return

        changes = []
        affected = []
        old_merges = set(self._template.merge_ranges)
        full_cell_paste = paste_text and paste_style

        for tr, tc, sr, sc in mapping:
            if tr >= self._template.rows or tc >= self._template.cols:
                continue

            payload = clipboard["cells"][(sr, sc)]
            text = payload[0] if len(payload) >= 1 else ""
            style = payload[1] if len(payload) >= 2 else None
            source_cell_data = payload[2] if len(payload) >= 3 else None

            if paste_text:
                old_cd = self._template.get_cell_data(tr, tc)
                if full_cell_paste and source_cell_data is not None:
                    old_dict = old_cd.to_dict()
                    new_cd = CellData.from_dict(source_cell_data)
                    new_dict = new_cd.to_dict()
                    if old_dict != new_dict:
                        self._template.set_cell_data(tr, tc, new_cd)
                        changes.append(("cell_data", tr, tc, old_dict, new_dict))
                else:
                    old_text = old_cd.static_text or ""
                    if old_text != text:
                        old_cd.static_text = text
                        self._template.set_cell_data(tr, tc, old_cd)
                        changes.append(("text", tr, tc, old_text, text))

            if paste_style and style is not None:
                old_style = self._template.cell_styles.get((tr, tc))
                old_copy = old_style.clone() if old_style else None
                new_style = style.clone()
                if old_copy != new_style:
                    self._template.set_cell_style(tr, tc, new_style)
                    changes.append(("style", tr, tc, old_copy, new_style))

            affected.append((tr, tc))

        if paste_style and clipboard.get("merges") and affected:
            min_r = min(r for r, _ in affected)
            min_c = min(c for _, c in affected)
            source_h, source_w = clipboard["height"], clipboard["width"]
            target_h = max(r for r, _ in affected) - min_r + 1
            target_w = max(c for _, c in affected) - min_c + 1
            for tile_r in range(0, target_h, source_h):
                for tile_c in range(0, target_w, source_w):
                    for top, bottom, left, right in clipboard["merges"]:
                        t, b = min_r + tile_r + top, min_r + tile_r + bottom
                        l, rr = min_c + tile_c + left, min_c + tile_c + right
                        if b < self._template.rows and rr < self._template.cols:
                            self._template.add_merge_range(t, b, l, rr)
            if old_merges != self._template.merge_ranges:
                changes.append(("merges", old_merges, set(self._template.merge_ranges)))

        self._undo_mgr.record_batch(changes)
        self._preview.refresh_all()
        if affected:
            self._preview.select_cells(affected, affected[0])
        self._status_label.setText(f"已粘贴到 {len(affected)} 个单元格")
        if after_change:
            after_change()

    editor._paste_from_clipboard = MethodType(paste_from_clipboard, editor)

    # 原 QAction/PreviewTable 信号在 MainWindow 初始化时已经绑定到原 _copy，
    # 因此在原复制动作之后追加一次“剪贴板升级”即可。
    editor._preview.copy_requested.connect(upgrade_internal_clipboard)

    def notify(*_args):
        if after_change:
            after_change()

    # 菜单和工具栏中的 QAction 追加后处理。Qt 会按连接顺序先执行原动作，
    # 再执行这里的升级/刷新，因此不需要拆掉 MainWindow 已有信号。
    for action in editor.findChildren(QAction):
        text = (action.text() or "").replace("&", "")
        if text == "复制" or text.startswith("复制("):
            action.triggered.connect(upgrade_internal_clipboard)
        if (text.startswith("撤销") or text.startswith("恢复") or
                text.startswith("粘贴") or text.startswith("仅粘贴") or
                text.startswith("格式粘贴") or text.startswith("合并") or
                text.startswith("取消合并") or text.startswith("插入行") or
                text.startswith("删除行") or text.startswith("插入列") or
                text.startswith("删除列")):
            action.triggered.connect(notify)

    editor._preview.undo_requested.connect(notify)
    editor._preview.redo_requested.connect(notify)
    editor._preview.paste_requested.connect(notify)
