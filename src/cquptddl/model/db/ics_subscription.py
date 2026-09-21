from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel


class IcsSubscription(SQLModel, table=True):
    """ICS日历订阅，一个用户可以有多条"""

    id: UUID = Field(default_factory=uuid7, primary_key=True, description="订阅id")
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    token_hash: str = Field(
        unique=True,
        index=True,
        description="订阅token的sha256，明文只在创建时返回一次",
    )
    created_at: datetime = Field(
        description="创建时间，同时用作事件的DTSTAMP",
        default_factory=lambda: datetime.now().astimezone(),
    )
    fetch_count: int = Field(default=0, description="被拉取次数")
    last_fetched_at: datetime | None = Field(
        default=None, description="最后一次拉取时间"
    )
