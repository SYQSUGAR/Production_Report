"""用户身份模型 —— 区分管理员与普通使用者。"""

from enum import Enum


class UserRole(Enum):
    ADMIN = "admin"          # 管理员：拥有全部模板编辑权限
    VIEWER = "viewer"        # 普通人员：仅能选择日期拉取数据生成报表


class UserSession:
    """管理当前登录用户的状态。"""

    def __init__(self, role: UserRole = UserRole.ADMIN):
        self._role = role
        self._selected_date = None  # 普通用户选择的报表日期

    @property
    def role(self) -> UserRole:
        return self._role

    def set_role(self, role: UserRole):
        self._role = role

    @property
    def is_admin(self) -> bool:
        return self._role == UserRole.ADMIN

    @property
    def is_viewer(self) -> bool:
        return self._role == UserRole.VIEWER

    @property
    def selected_date(self):
        return self._selected_date

    def set_selected_date(self, date):
        self._selected_date = date

    def to_dict(self) -> dict:
        return {
            "role": self._role.value,
            "selected_date": str(self._selected_date) if self._selected_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserSession":
        session = cls(UserRole(data.get("role", "admin")))
        from datetime import date
        if data.get("selected_date"):
            session._selected_date = date.fromisoformat(data["selected_date"])
        return session
