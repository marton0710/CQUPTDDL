from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Cookie


class CookieRepositories:
    """cookie数据库操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_cookie(self, platform: str, cookies: dict[str, str]) -> Cookie:
        """
        新建cookie
        :param platform: 平台
        :param cookies: cookie内容
        :return: Cookie对象
        """
        new_cookie = Cookie(
            platform=platform,
            cookies=cookies,
        )
        self.session.add(new_cookie)
        await self.session.flush()
        return new_cookie

    async def get_cookie(self, platform: str) -> Cookie | None:
        """
        获取cookie
        :param platform: 平台
        :return: Cookie对象
        """
        stmt = select(Cookie).where(Cookie.platform == platform)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_cookie(self, platform: str, cookies: dict[str, str]) -> None:
        """
        更新平台cookie
        :param platform: 平台
        :param cookies: 新的cookie
        :return:
        """
        stmt = (
            update(Cookie)
            .where(Cookie.platform == platform)
            .values(cookies=cookies)
        )
        await self.session.execute(stmt)
