from datetime import time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QQPushStrategyEnum(StrEnum):
    SCHEDULED = "scheduled"
    REALTIME = "realtime"


class QQPushConfigSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qqchan_id: str | None = None
    qq_push_strategy: QQPushStrategyEnum = Field(
        QQPushStrategyEnum.SCHEDULED, description="推送策略"
    )
    qq_push_at: time = Field(time(7), description="定时推送时刻")
    qq_push_scope: int = Field(
        24, description="推送从推送时刻开始多长时间内截止的作业。单位：时"
    )
