from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import await_only

from app.db.models import Cookie


class CookieRepositories:
    """cookie数据库操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_cookie(
            self,
            user_id: int,
            platform: str,
            cookies: dict[str, str],
    ) -> Cookie:
        """
        新建cookie
        :param user_id: 用户id
        :param platform: 平台
        :param cookies: cookie内容
        :return: Cookie对象
        """
        new_cookie = Cookie(
            user_id=user_id,
            platform=platform,
            cookies=cookies,
        )
        self.session.add(new_cookie)
        await self.session.flush()
        return new_cookie

    async def get_cookie(self, user_id: int, platform: str) -> Cookie | None:
        """
        获取cookie
        :param user_id: 用户id
        :param platform: 平台
        :return: Cookie对象或空
        """
        stmt = (
            select(Cookie)
            .where(Cookie.user_id == user_id)
            .where(Cookie.platform == platform)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_cookie(
            self,
            user_id: int,
            platform: str,
            cookies: dict[str, str],
    ) -> None:
        """
        更新cookie
        :param user_id: 用户id
        :param platform: 平台
        :param cookies: 新的cookie
        :return:
        """
        stmt = (
            update(Cookie)
            .where(Cookie.user_id == user_id)
            .where(Cookie.platform == platform)
            .values(cookies=cookies)
        )
        await self.session.execute(stmt)

    async def save_cookies(
            self,
            user_id: int,
            platform: str,
            cookies: dict[str, str]
    ) -> Cookie:
        """
        保存cookie，有则更新，无则创建
        :param user_id: 用户id
        :param platform: 平台
        :param cookies: cookie
        :return: Cookie对象
        """
        row = await self.get_cookie(user_id=user_id, platform=platform)
        if row:
            await self.update_cookie(
                user_id=user_id,
                platform=platform,
                cookies=cookies,
            )
            return row
        return await self.create_cookie(user_id=user_id, platform=platform, cookies=cookies)
