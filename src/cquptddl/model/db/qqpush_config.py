from datetime import time

from sqlmodel import Field, SQLModel

from cquptddl.model.schema.qqpush import QQPushStrategyEnum


class QQPushConfig(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    qqchan_id: str | None = Field(None, description="绑定id", index=True)
    qq_push_strategy: QQPushStrategyEnum = Field(
        QQPushStrategyEnum.SCHEDULED, description="推送策略"
    )
    qq_push_at: time = Field(time(7), description="定时推送时刻")
    qq_push_scope: int = Field(
        24, description="推送从推送时刻开始多长时间内截止的作业。单位：时", ge=1
    )
