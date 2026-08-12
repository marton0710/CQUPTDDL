from abxbus import BaseEvent

from cquptddl.model.db import User


class UserReloginRequiredEvent(BaseEvent):
    uid: str


class UserRegisterEvent(BaseEvent):
    user: User


class UserLoginEvent(BaseEvent):
    user: User
