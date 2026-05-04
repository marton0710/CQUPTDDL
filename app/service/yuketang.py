import httpx

from app.utils import Error
from app.adapter.platform.yuketang import Yuketang
from app.schemas import Homework


class YuKeTangService:
    """长江雨课堂服务层"""

    def __init__(self, cookies: dict[str, str]):
        self.cookies = cookies
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.platform = Yuketang().name
        self.client = httpx.AsyncClient(
            headers=self.headers,
            cookies=self.cookies,
            timeout=10,
        )

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
