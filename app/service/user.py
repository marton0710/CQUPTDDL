from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import UserRepositories
from app.utils import Error, hash_password, verify_password, create_access_token


class UserService:
    """用户服务层"""

    def __init__(
            self,
            session: AsyncSession,
            username: str,
            password: str,
            email: str,
            confirm_password: str | None = None,
    ):
        self.session = session
        self.username = username
        self.password = password
        self.email = email
        self.confirm_password = confirm_password
        self.repo = UserRepositories(session=session)

    async def add_new_user(self) -> str:
        """
        添加新用户并返回username
        :return: username
        """
        if self.password != self.confirm_password:
            raise Error(code=400, message="两次密码不一致")

        if await self.repo.get_user(username=self.username, email=self.email):
            raise Error(code=400, message="用户名已存在")

        new_user = await self.repo.create_user(
            username=self.username,
            password=hash_password(self.password),
            email=self.email,
        )
        await self.session.commit()
        return new_user.username

    async def login(self) -> str:
        """
        登录
        :return: jwt token
        """
        row = await self.repo.get_user(username=self.username, email=self.email)

        if not row:
            raise Error(code=400, message="用户名或邮箱或密码错误")

        if not verify_password(self.password, row.hashed_password):
            raise Error(code=400, message="用户名或邮箱或密码错误")

        access_token = create_access_token(
            data={"sub": row.username},
        )
        return access_token
