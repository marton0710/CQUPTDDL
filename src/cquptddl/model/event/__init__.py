from abxbus import BaseEvent


class UserReloginRequiredEvent(BaseEvent):
    uid: str
