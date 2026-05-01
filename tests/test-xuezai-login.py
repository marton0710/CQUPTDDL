import getpass
from unittest import IsolatedAsyncioTestCase

from httpx import AsyncClient

from app.adapter.platform.xuezai import Xuezai


class TestXueZaiLogin(IsolatedAsyncioTestCase):
    async def test_login(self):
        await Xuezai.login(AsyncClient(), input("username> "), getpass.getpass())
