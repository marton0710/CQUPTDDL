from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from cquptddl.model.schema.platform_auth import PlatformEnum


class PlatformInfo(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    platform: PlatformEnum = Field(description="平台名称", primary_key=True)
    credentials: str = Field(description="加密后的平台登录凭据")
    cookies: dict[str, str] = Field(description="平台cookies", sa_type=JSON)
    last_refreshed_homework: datetime = Field(description="上次刷新作业的时间")
