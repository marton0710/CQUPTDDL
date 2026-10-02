from abxbus import BaseEvent

from cquptddl.model.schema.platform import PlatformEnum


class UserReloginRequiredEvent(BaseEvent):
    uid: str


class AutoRefreshHomeworkFailedEvent(BaseEvent):
    uid: str
    platform_name: PlatformEnum
    exc: Exception
