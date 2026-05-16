import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import CookieRepositories
from app.service.cache_service import CacheService
from app.schemas import Homework
from app.utils import Error

from app.adapter.platform.chaoxing import Chaoxing


class ChaoXingService:
    """超星学习通服务层"""

    def __init__(
            self,
            username: str,
            password: str,
            session: AsyncSession,
            owner: str,
    ):
        self.username = username
        self.password = password
        self.session = session
        self.owner = owner
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
            )
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=15,
        )
        self.platform = Chaoxing().name

    async def _chaoxing_login(self) -> None:
        """
        超星登陆
        :return:
        """
        await Chaoxing.login(
            client=self.client,
            username=self.username,
            password=self.password,
        )

    async def _get_chaoxing_homework(self) -> list[Homework]:
        """
        获取超星作业
        :return: 作业列表
        """
        await self._chaoxing_login()
        homework: list[Homework] = await Chaoxing.get_homework(
            client=self.client,
        )
        return homework

    async def refresh_homework(self) -> dict:
        """
        重新获取超星作业
        :return:
        """
        try:
            cache = CacheService()
            cached = await cache.get_cached_homework(
                username=self.owner,
                platform=self.platform,
            )
            if cached is not None and await cache.in_cooldown(
                    username=self.owner,
                    platform=self.platform,
            ):
                return {
                    "errcode": 0,
                    "username": self.owner,
                    "homework": cached,
                }
            homework = await self._get_chaoxing_homework()

            await CookieRepositories(session=self.session).save_cookies(
                user_id=self.owner,
                platform=self.platform,
                cookies={
                    cookie.name: cookie.value
                    for cookie in self.client.cookies.jar
                },
            )
            await self.session.commit()

            await CacheService().set_homework_cache(
                username=self.owner,
                platform=self.platform,
                homework=homework,
            )

            return {
                "errcode": 0,
                "username": self.owner,
                "homework": homework,
            }
        except Error:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise Error(
                code=400,
                message=f"{self.platform}获取作业失败: {e}",
            ) from e
        finally:
            await self.close()


    async def close(self):
        """
        关闭client
        :return:
        """
        await self.client.aclose()
