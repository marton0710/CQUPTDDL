from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from cquptddl.model.schema.platform_auth import PlatformEnum


class PlatformCookies(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    platform: PlatformEnum = Field(description="平台名称", primary_key=True)
    cookies: dict[str, str] = Field(description="平台cookies", sa_type=JSON)
