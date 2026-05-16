import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Awaitable, Callable

from app.db.models import User
from app.db.repositories import CookieRepositories
from app.service.cache_service import CacheService
from app.schemas import Homework
from app.utils import Error

from app.adapter.platform.yuketang import Yuketang
from app.adapter.platform.chaoxing import Chaoxing
from app.adapter.platform.xuezai import Xuezai


class AllHomeworkService:
    def __init__(self, session: AsyncSession, current_user: User):
        self.session = session
        self.current_user = current_user
        self.cache = CacheService()
        self.cookie_repo = CookieRepositories(session=session)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
            )
        }

    async def get_all_homework(self) -> dict:
        """
        获取全部作业
        :return:
        """
        um = self.current_user.username
        return {
            "errcode": 0,
            "username": um,
            "data": {
                "chaoxing": await self._get_platform_homework(
                    username=um,
                    platform=Chaoxing().name,
                    fetcher=self._fetch_chaoxing_homework,
                ),
                "xuezai": await self._get_platform_homework(
                    username=um,
                    platform=Xuezai().name,
                    fetcher=self._fetch_xuezai_homework,
                ),
                "yuketang": await self._get_platform_homework(
                    username=um,
                    platform=Yuketang().name,
                    fetcher=self._fetch_yuketang_homework,
                ),
            }
        }

    async def _get_platform_homework(
            self,
            username: str,
            platform: str,
            fetcher: Callable[[dict[str, str]], Awaitable[list[Homework]]],
    ) -> dict:
        """
        获取平台作业
        :param username: 用户名
        :param platform: 平台
        :param fetcher: 具体函数
        :return:
        """
        cached = await self.cache.get_cached_homework(
            username=username,
            platform=platform,
        )
        if cached is not None and await self.cache.in_cooldown(
            username=username,
            platform=platform,
        ):
            return {
                "errcode": 0,
                "homework": cached,
            }

        cookie_row = await self.cookie_repo.get_cookie(
            user_id=username,
            platform=platform,
        )
        if cookie_row is None:
            return {
                "errcode": 1,
                "homework": cached or [],
            }

        try:
            homework = await fetcher(cookie_row.cookies)
            await self.cache.set_homework_cache(
                username=username,
                platform=platform,
                homework=homework,
            )
            return {
                "errcode": 0,
                "homework": homework,
            }
        except Exception:
            return {
                "errcode": 1,
                "homework": cached or [],
            }

    async def _fetch_yuketang_homework(self, cookies: dict[str, str]) -> list[Homework]:
        """
        获取雨课堂作业
        :param cookies: cookies
        :return:
        """
        if not await Yuketang.valid_cookie(cookie_dict=cookies):
            raise Error(code=401, message="雨课堂请重新登录")

        async with httpx.AsyncClient(
            headers=self.headers,
            cookies=cookies,
            timeout=15,
        ) as client:
            return await Yuketang.get_homework(client=client)

    async def _fetch_xuezai_homework(self, cookies: dict[str, str]) -> list[Homework]:
        """
        获取学在重邮作业
        :param cookies: cookies
        :return:
        """
        if not True:
            raise Error(code=401, message="学在重邮请重新登录")

        async with httpx.AsyncClient(
            headers=self.headers,
            cookies=cookies,
            timeout=15,
        ) as client:
            return await Xuezai.get_homework(client=client)

    async def _fetch_chaoxing_homework(self, cookies: dict[str, str]) -> list[Homework]:
        if not True:
            raise Error(code=401, message="学习通请重新登录")

        async with httpx.AsyncClient(
            headers=self.headers,
            cookies=cookies,
            timeout=15,
        ) as client:
            return await Chaoxing.get_homework(client=client)
