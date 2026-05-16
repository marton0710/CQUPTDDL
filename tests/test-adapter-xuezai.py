from getpass import getpass
from pprint import pprint
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.xuezai import Xuezai


class TestXueZaiLogin(IsolatedAsyncioTestCase):
    cookie = []

    async def asyncSetUp(self):
        self.client = AsyncClient()

    async def test_1_login(self):
        await Xuezai.login(self.client, input("username> "), getpass())
        self.cookie.append(self.client.cookies)

    async def test_2_get_homework(self):
        self.client.cookies = self.cookie[0]
        hmw = await Xuezai.get_homework(self.client)
        pprint(hmw)

    async def test_3_valid_cookie(self):
        self.assertTrue(await Xuezai.valid_cookie(self.cookie[0]))

    async def test_4_invalid_cookie(self):
        self.assertFalse(await Xuezai.valid_cookie({}))

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
