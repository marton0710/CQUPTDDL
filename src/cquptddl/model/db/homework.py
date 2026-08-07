import uuid
from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

UUID_NAMESPACE_HOMEWORK_ID = uuid.UUID("6db7a68c-8723-4b63-87c8-876e32eda418")


class PlatformEnum(StrEnum):
    XZCY = "学在重邮"
    CHAOXING = "学习通"
    YUKETANG = "雨课堂"


class AuthMethod(StrEnum):
    CQUPT_IDS = "cqupt_ids"  # 使用当前用户的统一认证账号登录
    PASSWORD = "password"  # 使用独立密码登录


class Homework(SQLModel, table=True):
    """
    作业信息
    """

    id: uuid.UUID = Field(
        description="作业id = uuid5(platform+course_name + title)",
        primary_key=True,
    )
    course_name: str = Field("", description="课程名称")
    title: str = Field(description="作业标题")
    deadline: datetime | None = Field(description="作业截止时间")
    url: str | None = Field(description="作业链接")
    platform: PlatformEnum = Field(description="作业平台")
    done: bool = Field(False, description="是否已完成")

    @staticmethod
    def generate_id(platform: str, course_name: str, title: str) -> uuid.UUID:
        return uuid.uuid5(
            UUID_NAMESPACE_HOMEWORK_ID,
            platform + course_name + title,
        )
