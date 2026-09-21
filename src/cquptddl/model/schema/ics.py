from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IcsSubscriptionSchema(BaseModel):
    """
    ICS订阅信息。token当成密码只存哈希，**不会**在这里返回，
    前端用 `id` 区分自己的多条订阅
    """

    id: UUID = Field(description="订阅id，删除时使用")
    created_at: datetime = Field(description="创建时间")
    fetch_count: int = Field(0, description="被拉取次数")
    last_fetched_at: datetime | None = Field(None, description="最后一次拉取时间")


class IcsSubscriptionCreatedSchema(IcsSubscriptionSchema):
    """仅POST创建时返回，`token` 明文只出现这一次"""

    token: str = Field(description="订阅凭据，拼成 `/api/ics/feed/{token}.ics`")
