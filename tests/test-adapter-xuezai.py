import getpass
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.xuezai import Xuezai


class TestXueZaiLogin(IsolatedAsyncioTestCase):
    cookie = []

    async def asyncSetUp(self):
        self.client = AsyncClient()

    async def test_1_login(self):
        await Xuezai.login(self.client, input("username> "), getpass.getpass())
        self.cookie.append(self.client.cookies)
        print(self.client.cookies)

    async def test_2_get_homework(self):
        self.client.cookies = self.cookie[0]
        hmw = await Xuezai.get_homework(self.client)
        print(hmw)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
