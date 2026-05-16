from getpass import getpass
from pprint import pprint
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.chaoxing import Chaoxing


class TestChaoxingLogin(IsolatedAsyncioTestCase):
    client = AsyncClient()

    async def test_1_login(self):
        await Chaoxing.login(
            client=self.client,
            username=input("username> "),
            password=getpass(),
        )

    async def test_2_get_homework(self):
        hmw = await Chaoxing.get_homework(
            client=self.client,
        )
        pprint(hmw)

    async def test_3_valid_cookie(self):
        self.assertTrue(await Chaoxing.valid_cookie(self.client.cookies))

    async def test_4_invalid_cookie(self):
        self.assertFalse(await Chaoxing.valid_cookie({}))
