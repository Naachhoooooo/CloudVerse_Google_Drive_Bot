from enum import Enum, auto
from typing import Any, Dict, Optional

class UserStateEnum(Enum):
    IDLE = auto()
    EXPECTING_DEV_MESSAGE = auto()
    EXPECTING_DELETE_CONFIRMATION = auto()
    EXPECTING_APPROVAL_MESSAGE = auto()
    EXPECTING_CODE = auto()
    EXPECTING_LOGOUT_CONFIRMATION = auto()
    EXPECTING_ADMIN_USERNAME = auto()
    EXPECTING_WHITELIST_USERNAME = auto()
    EXPECTING_LIMIT_HOURS = auto()
    EXPECTING_PARALLEL_UPLOADS = auto()
    FILE_MANAGER = auto()
    SEARCH = auto()
    MENU = auto()
    ADMIN_CONTROL = auto()
    TERMS = auto()
    CLOUDVERSE_SUPPORT = auto()
    AWAITING_DEV_REPLY = auto()
    AWAITING_USER_REPLY = auto()
    PERFORMANCE_PANEL = auto()

class UserState:
    def __init__(self):
        self.state: UserStateEnum = UserStateEnum.IDLE
        self.data: Dict[str, Any] = {}

    def set_state(self, new_state: UserStateEnum, data: Optional[Dict[str, Any]] = None):
        self.state = new_state
        self.data = data or {}

    def reset(self):
        self.state = UserStateEnum.IDLE
        self.data = {}

    def is_state(self, state: UserStateEnum) -> bool:
        return self.state == state

    def __repr__(self):
        return f"<UserState state={self.state} data={self.data}>" 