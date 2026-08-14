from abxbus import BaseEvent

from cquptddl.model.db import User
from cquptddl.model.schema.platform_auth import PlatformEnum


class UserReloginRequiredEvent(BaseEvent):
    uid: str


class UserRegisterEvent(BaseEvent):
    user: User


class UserLoginEvent(BaseEvent):
    user: User


class HomeworkRefreshedEvent(BaseEvent):
    user: User
    platform_name: PlatformEnum
