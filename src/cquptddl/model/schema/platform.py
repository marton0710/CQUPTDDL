from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PlatformEnum(StrEnum):
    XZCY = "学在重邮"
    CHAOXING = "学习通"
    YUKETANG = "雨课堂"


class BaseAuthInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IDSLoginInput(BaseAuthInputModel):
    pass


class PasswordLoginInput(BaseAuthInputModel):
    username: str
    password: str


AllAuthInputs = IDSLoginInput | PasswordLoginInput


class AuthMethod(StrEnum):
    model_class: type[AllAuthInputs]

    CQUPT_IDS = ("cqupt_ids", IDSLoginInput)  # 使用当前用户的统一认证账号登录
    PASSWORD = ("password", PasswordLoginInput)  # 使用独立密码登录

    def __new__(cls, name: str, model_class: type[AllAuthInputs]):
        obj = str.__new__(cls, name)
        obj._value_ = name
        obj.model_class = model_class
        return obj
