from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


class Homework(BaseModel):
    """
    作业信息
    """

    title: str = Field(description="作业标题")
    content: str = Field(description="作业内容")
    deadline: datetime | None = Field(description="作业截止时间")
    url: str = Field(description="作业链接")
    platform: str = Field(description="作业平台")

    @field_serializer("deadline")
    def serialize_deadline(self, value: datetime | None) -> int:
        if value is None:
            return 0
        return int(value.timestamp())
