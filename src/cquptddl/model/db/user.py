from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import JSON, Field, SQLModel


class User(SQLModel, table=True):
    id: str = Field(description="统一认证码", primary_key=True)
    password: str | None = Field(description="统一认证密码，若为扫码登录则为None")
    ids_cookie: dict = Field({}, description="重邮统一认证平台cookie", sa_type=JSON)
    name: str
    email: str | None = None
    qqchan_id: str | None = None
    meetschedule_key: str | None = Field(None, unique=True)

    @classmethod
    async def from_uid(
        cls,
        session: AsyncSession,
        uid: str,
    ) -> User | None:
        return await session.get(cls, uid)
