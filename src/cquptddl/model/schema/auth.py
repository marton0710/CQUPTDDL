from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginInput(BaseModel):
    username: str
    password: str


class LoginOutput(BaseModel):
    name: str = Field(description="用户姓名")


class Userinfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # name: str = Field(description="用户姓名")
    email: EmailStr | None = None
    qqchan_id: str | None = None
    meetschedule_key: str | None = None
