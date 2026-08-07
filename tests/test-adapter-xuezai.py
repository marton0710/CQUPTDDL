from pprint import pprint
from typing import ClassVar
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from cquptddl.service.homework.platform import Xzcy


class TestXueZaiLogin(IsolatedAsyncioTestCase):
    cookie: ClassVar[list] = []

    async def asyncSetUp(self):
        self.client = AsyncClient()

    async def test_1_login(self):
        await Xzcy.login(self.client)
        self.cookie.append(self.client.cookies)

    async def test_2_get_homework(self):
        self.client.cookies = self.cookie[0]
        hmw = await Xzcy.get_homework(self.client)
        pprint(hmw)

    async def test_3_valid_cookie(self):
        self.assertTrue(await Xzcy.valid_cookie(self.cookie[0]))

    async def test_4_invalid_cookie(self):
        self.assertFalse(await Xzcy.valid_cookie({}))

    async def test_3_valid_cookie(self):
        self.assertTrue(await Xzcy.valid_cookie(self.cookie[0]))

    async def test_4_invalid_cookie(self):
        self.assertFalse(await Xzcy.valid_cookie({}))

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
