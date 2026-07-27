"""模板持久化 —— JSON 格式保存 / 加载全套模板配置。"""

import json
from pathlib import Path
from typing import Optional

from models.template_model import TemplateModel


class TemplateIO:
    """负责模板的 JSON 文件读写。"""

    @staticmethod
    def save(template: TemplateModel, filepath: str):
        """将模板保存为 JSON 文件。"""
        data = template.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(filepath: str) -> Optional[TemplateModel]:
        """从 JSON 文件加载模板。"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TemplateModel.from_dict(data)

    @staticmethod
    def save_as(template: TemplateModel, filepath: str):
        """另存为 JSON 文件（同 save，语义区分）。"""
        TemplateIO.save(template, filepath)
