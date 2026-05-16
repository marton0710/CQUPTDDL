from getpass import getpass
from pprint import pprint
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.yuketang import Yuketang


class TestYuketang(IsolatedAsyncioTestCase):
    cookie = []

    async def test_1_login(self):
        client = AsyncClient()
        await Yuketang.login(client, input("username> "), getpass())
        self.cookie.append({"sessionid": client.cookies.get("sessionid")})

    async def test_2_get_homework(self):
        client = AsyncClient(cookies=self.cookie[0])
        homework = await Yuketang.get_homework(client)
        pprint(homework)

    async def test_3_valid_cookie(self):
        self.assertTrue(await Yuketang.valid_cookie(self.cookie[0]))

    async def test_4_invalid_cookie(self):
        self.assertFalse(await Yuketang.valid_cookie({}))
