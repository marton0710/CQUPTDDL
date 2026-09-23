from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import UUID5, BaseModel, Field, field_serializer

from cquptddl.core.config import config
from cquptddl.model.schema.platform import PlatformEnum

# 库内时间统一按UTC存储，对外按配置时区展示，避免各客户端各自换算
_DISPLAY_TZ = ZoneInfo(config.ics_timezone)


class Homework(BaseModel):
    """
    作业信息
    """

    id: UUID5 | None = Field(
        None,
        description="作业id = uuid5(platform + course_name + title)",
    )
    course_name: str = Field("", description="课程名称")
    title: str = Field(description="作业标题")
    deadline: datetime | None = Field(None, description="作业截止时间")
    url: str | None = Field(None, description="作业链接")
    platform: PlatformEnum = Field(description="作业平台")
    done: bool = Field(False, description="是否已完成")

    @field_serializer("deadline")
    def serialize_deadline(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(_DISPLAY_TZ)

    # @model_validator(mode="after")
    # def generate_id(self) -> Homework:
    #     if self.id is None:
    #         self.id = uuid.uuid5(
    #             UUID_NAMESPACE_HOMEWORK_ID,
    #             self.course_name + self.title + self.platform,
    #         )
    #     return self


class HomeworkResponse(BaseModel):
    count: int
    last_refresh_time: datetime
    homeworks: list[Homework]

    @field_serializer("last_refresh_time")
    def serialize_last_refresh_time(self, value: datetime) -> datetime:
        return value.astimezone(_DISPLAY_TZ)


class HomeworkCompleteInput(BaseModel):
    is_complete: bool
