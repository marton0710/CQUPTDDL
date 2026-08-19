from pydantic import BaseModel, ConfigDict, Field

from cquptddl.model.schema.meetschedule import MeetscheduleConfigSchema
from cquptddl.model.schema.qqpush import QQPushConfigSchema


class LoginInput(BaseModel):
    username: str
    password: str


class LoginOutput(BaseModel):
    name: str = Field(description="用户姓名")


class Userinfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="用户姓名")
    qqpush_config: QQPushConfigSchema = Field(description="qq推送配置")
    meetschedule_config: MeetscheduleConfigSchema = Field(
        description="meet课程表同步配置"
    )
