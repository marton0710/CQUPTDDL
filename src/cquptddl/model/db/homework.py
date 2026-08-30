import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from cquptddl.model.schema.platform import PlatformEnum

UUID_NAMESPACE_HOMEWORK_ID = uuid.UUID("6db7a68c-8723-4b63-87c8-876e32eda418")


class Homework(SQLModel, table=True):
    """
    作业信息
    """

    id: uuid.UUID = Field(
        description="作业id = uuid5(user_id + platform + course_name + title)",
        primary_key=True,
    )
    user_id: str = Field(
        description="用户id", foreign_key="user.id", ondelete="CASCADE"
    )
    course_name: str = Field("", description="课程名称")
    title: str = Field(description="作业标题")
    deadline: datetime | None = Field(description="作业截止时间")
    url: str | None = Field(description="作业链接")
    platform: PlatformEnum = Field(description="作业平台")
    done: bool = Field(False, description="是否已完成")

    @staticmethod
    def generate_id(
        user_id: str, platform: str, course_name: str, title: str
    ) -> uuid.UUID:
        return uuid.uuid5(
            UUID_NAMESPACE_HOMEWORK_ID,
            user_id + platform + course_name + title,
        )

    def __eq__(self, b):
        if not isinstance(b, Homework):
            return False
        return self.id == b.id

    def __hash__(self):
        return hash(self.id)
