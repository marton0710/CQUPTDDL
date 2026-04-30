from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import UserRepositories


class UserService:
    """用户服务层"""

    def __init__(self, session: AsyncSession, username: str):
        self.session = session
        self.username = username
        self.repo = UserRepositories(session=session)

    async def add_new_user(self) -> int:
        """
        添加新用户并返回user_id
        :return: user_id
        """
        new_user = await self.repo.create_user(username=self.username)
        await self.session.commit()
        return new_user.id
