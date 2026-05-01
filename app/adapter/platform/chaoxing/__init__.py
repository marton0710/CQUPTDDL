from datetime import datetime

from httpx import AsyncClient

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.chaoxing.urls import LOGIN_URL
from app.adapter.platform.chaoxing.utils import encryptByAES
from app.schemas.homework import Homework
from app.utils.error import LoginFailed


class Chaoxing(BasePlatform):
    @property
    def name(self):
        return "学习通"

    @staticmethod
    async def login(client: AsyncClient, username: str, password: str):
        uid_enc = encryptByAES(username)
        psw_enc = encryptByAES(password)

        data = {
            "fid": -1,
            "uname": uid_enc,
            "password": psw_enc,
            "refer": "https://i.xuexitong.com",
            "t": "true",
            "forbidotherlogin": 0,
            "validate": "",
            "doubleFactorLogin": 0,
            "independentId": 0,
            "independentNameId": 0,
        }

        resp = await client.post(
            url=LOGIN_URL,
            data=data,
            follow_redirects=True,
        )
        resp_data = resp.json()
        if not resp_data["status"]:
            raise LoginFailed(resp_data.get("msg2", resp_data))

    async def get_homework(self):
        return Homework(
            content="",
            deadline=datetime.now(),
            platform=self.name,
            title="",
            url="",
        )
