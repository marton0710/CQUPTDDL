from abxbus import BaseEvent

from cquptddl.model.schema.platform import PlatformEnum


class UserReloginRequiredEvent(BaseEvent):
    uid: str


class UserRegisterEvent(BaseEvent):
    uid: str


class UserLoginEvent(BaseEvent):
    uid: str


class HomeworkRefreshedEvent(BaseEvent):
    uid: str
    platform_name: PlatformEnum


class PlatformBoundEvent(BaseEvent):
    uid: str
    platform_name: PlatformEnum


class PlatformUnboundEvent(BaseEvent):
    uid: str
    platform_name: PlatformEnum


class AutoRefreshHomeworkFailedEvent(BaseEvent):
    uid: str
    platform_name: PlatformEnum
    exc: Exception


class AccountDeletedEvent(BaseEvent):
    uid: str


class QQPushConfigChangedEvent(BaseEvent):
    uid: str


class InvalidQQChanIDEvent(BaseEvent):
    uid: str
