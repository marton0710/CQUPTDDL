from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.yuketang import Yuketang


class TestYuketang(IsolatedAsyncioTestCase):
    cookie = []

    async def test_1_login(self):
        cookies = await Yuketang.login()
        self.cookie.append(cookies)
        print(cookies)

    async def test_2_get_homework(self):
        client = AsyncClient(cookies=self.cookie[0])
        homework = await Yuketang.get_homework(client)
        print(homework)
