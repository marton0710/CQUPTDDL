from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import CookieRepositories
from app.utils import Error


class BaseCookieService(ABC):
    """cookie基本服务"""

    platform: str = ""

    def __init__(self, session: AsyncSession, user_id: int):
        self.session = session
        self.user_id = user_id
        self.repo = CookieRepositories(session=session)

    async def get_avalible_cookie(self) -> dict[str, str]:
        """
        获取可用cookie
        :return: cookie
        """
        try:
            row = await self.repo.get_cookie(
                user_id=self.user_id,
                platform=self.platform
            )
            if row and await self._valid_cookie(cookie_dict=row.cookies):
                return row.cookies
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"未知错误：{e}")

        try:
            cookies = await self._login_and_get_cookie()
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"未知错误：{e}")

        await self.repo.save_cookies(
            user_id=self.user_id,
            platform=self.platform,
            cookies=cookies,
        )
        await self.session.commit()
        return cookies

    @abstractmethod
    async def _valid_cookie(self, cookie_dict: dict[str, str]) -> bool:
        """
        判断cookie有效性
        :param cookie_dict: cookie
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def _login_and_get_cookie(self) -> dict[str, str]:
        """
        重新登陆
        :return:
        """
        raise NotImplementedError
