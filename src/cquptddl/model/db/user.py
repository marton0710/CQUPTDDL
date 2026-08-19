from uuid import UUID, uuid7

from sqlmodel import JSON, Field, SQLModel


class User(SQLModel, table=True):
    id: str = Field(description="统一认证码", primary_key=True)
    password: str | None = Field(description="统一认证密码，若为扫码登录则为None")
    ids_cookie: dict = Field({}, description="重邮统一认证平台cookie", sa_type=JSON)
    name: str
    token_version: UUID = Field(
        description="token版本，用于退出登录", default_factory=uuid7
    )
