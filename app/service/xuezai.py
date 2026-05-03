import httpx

from app.db.repositories import CookieRepositories
from app.adapter.platform.xuezai import Xuezai
from app.schemas import Homework
from app.utils import Error


class XueZaiService:
    """学在重邮服务层"""

    def __init__(self, username: str, password: str):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=10,
        )
        self.username = username
        self.password = password
        self.platform = Xuezai().name

    async def _xuezai_login(self) -> None:
        """
        学在重邮登陆
        :return:
        """
        await Xuezai.login(
            client=self.client,
            username=self.username,
            password=self.password,
        )

    async def get_xuezai_homework(self) -> list[Homework]:
        """
        获取学在重邮的作业
        :return: 作业列表
        """
        await self._xuezai_login()
        homework: list[Homework] = await Xuezai.get_homework(
            client=self.client,
        )
        return homework

    async def close(self):
        """
        关闭client
        :return:
        """
        await self.client.aclose()
