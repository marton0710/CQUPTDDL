from unittest import IsolatedAsyncioTestCase

from app.adapter.platform.yuketang import Yuketang


class TestYuketang(IsolatedAsyncioTestCase):
    async def test_login(self):
        cookies = await Yuketang.login()
        print(cookies)
