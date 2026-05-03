import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import CookieRepositories
from app.utils import Error
from app.adapter.platform.yuketang import Yuketang
from app.schemas import Homework


class YuKeTangService:
    """长江雨课堂服务层"""

    def __init__(self, session: AsyncSession, user_id: int):
        self.session = session
        self.user_id = user_id
        self.repo = CookieRepositories(session=session)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.platform = Yuketang().name
        self.client: httpx.AsyncClient | None = None

    @classmethod
    async def create(cls, session: AsyncSession, user_id: int):
        """
        初始化
        :param user_id: 用户id
        :param session: 数据库会话
        :return:
        """
        self = cls(session=session, user_id=user_id)
        cookies = await self._get_available_cookie()
        self.client = httpx.AsyncClient(
            headers=self.headers,
            cookies=cookies,
            timeout=10,
        )
        return self

    async def _get_available_cookie(self) -> dict[str, str]:
        """
        获取可用cookie
        :return: cookie字典
        """
        row = await self.repo.get_cookie(
            user_id=self.user_id,
            platform=self.platform,
        )
        if row and await Yuketang.valid_cookie(row.cookies):
            return row.cookies

        cookies = await Yuketang.login()
        await self.repo.save_cookies(
            user_id=self.user_id,
            platform=self.platform,
            cookies=cookies,
        )
        await self.session.commit()
        return cookies

    async def get_yuketang_homework(self) -> list[Homework]:
        """
        获取雨课堂作业
        :return: 作业列表
        """
        if self.client is None:
            raise Error(code=500, message=f"{self.platform}Client未打开")
        return await Yuketang.get_homework(self.client)

    async def close(self):
        """
        关闭client
        :return:
        """
        if self.client is not None:
            await self.client.aclose()
