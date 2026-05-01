import json
from datetime import datetime

from httpx import AsyncClient

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.chaoxing.urls import LOGIN_URL, NOTICE_URL
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

    @staticmethod
    async def get_homework(client: AsyncClient):
        data = (
            (
                await client.get(
                    url=NOTICE_URL,
                )
            )
            .raise_for_status()
            .json()["notices"]["list"]
        )
        homeworks: list[Homework] = []
        for item in data:
            try:
                msg_info = json.loads(item["extendParam"]["cparams"])["funConfig"]
                if msg_info["funTag"] != 3:
                    continue

                hmw_info = msg_info["content"]
                hmw_url = json.loads(item["attachment"])[0]["att_web"]["url"]
                homeworks.append(
                    Homework(
                        title=hmw_info["title"],
                        content=hmw_info["title"],
                        deadline=datetime.fromtimestamp(
                            int(hmw_info["endTime"]) / 1000
                        ),
                        course_name=hmw_info["courseName"],
                        url=hmw_url,
                        platform="学习通",
                    )
                )
            except Exception:
                homeworks.append(
                    Homework(
                        title="发现未知的收件箱",
                        content=json.dumps(item),
                        deadline=None,
                        course_name="警告",
                        url="about:blank",
                        platform="学习通",
                    )
                )
        return homeworks
