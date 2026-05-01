from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.chaoxing import Chaoxing


class TestChaoxingLogin(IsolatedAsyncioTestCase):
    async def test_login(self):
        chaoxing = Chaoxing()
        await chaoxing.login(
            client=AsyncClient(),
            username="",
            password="",
        )
