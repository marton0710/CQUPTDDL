import httpx

from app.adapter.platform.chaoxing import Chaoxing
from app.schemas import Homework


class ChaoXingService:
    """超星学习通服务层"""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=10,
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

    async def get_chaoxing_homework(self) -> list[Homework]:
        """
        获取超星作业
        :return: 作业列表
        """
        await self._chaoxing_login()
        homework: list[Homework] = await Chaoxing.get_homework(
            client=self.client,
        )
        return homework

    async def close(self):
        """
        关闭client
        :return:
        """
        await self.client.aclose()
