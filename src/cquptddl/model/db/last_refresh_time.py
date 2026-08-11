from datetime import datetime

from sqlmodel import Field, SQLModel

from cquptddl.model.schema.platform_auth import PlatformEnum


class LastRefreshTime(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    platform: PlatformEnum = Field(description="平台名称", primary_key=True)
    last_refreshed_homework: datetime = Field(description="上次刷新作业的时间")
