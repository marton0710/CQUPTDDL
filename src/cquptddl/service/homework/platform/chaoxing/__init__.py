import json
from datetime import datetime
from logging import INFO, getLogger

from httpx import AsyncClient
from httpx._types import CookieTypes

from cquptddl.exc import LoginFailed
from cquptddl.model.db import User
from cquptddl.model.db.homework import Homework
from cquptddl.model.schema.platform_auth import (
    AuthMethod,
    PasswordLoginInput,
    PlatformEnum,
)
from cquptddl.service.homework.platform.base import Platform as BasePlatform

from .urls import LOGIN_URL, NOTICE_URL
from .utils import encryptByAES

logger = getLogger(__name__)
logger.setLevel(INFO)


class Chaoxing(BasePlatform):
    name = PlatformEnum.CHAOXING
    auth_method = AuthMethod.PASSWORD

    @classmethod
    async def login(
        cls, client: AsyncClient, user, credentials: PasswordLoginInput
    ) -> dict[str, str]:  # ty: ignore[invalid-method-override]
        uid_enc = encryptByAES(credentials.username)
        psw_enc = encryptByAES(credentials.password)

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

        return dict(client.cookies)

    @classmethod
    async def get_homework(cls, client: AsyncClient, user: User) -> list[Homework]:
        data = (
            (await client.get(NOTICE_URL)).raise_for_status().json()["notices"]["list"]
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
                        id=Homework.generate_id(
                            user.id, cls.name, hmw_info["courseName"], hmw_info["title"]
                        ),
                        user_id=user.id,
                        title=hmw_info["title"],
                        deadline=datetime.fromtimestamp(
                            int(hmw_info["endTime"]) / 1000
                        ).astimezone(),
                        course_name=hmw_info["courseName"],
                        url=hmw_url,
                        platform=cls.name,
                    )
                )
            except Exception:  # noqa: BLE001
                logger.warning("发现未知的收件箱：%s", json.dumps(item))
                continue
                # homeworks.append(
                #     Homework(
                #         id=Homework.generate_id(
                #             cls.name, "警告", f"发现未知的收件箱：{json.dumps(item)}"
                #         ),
                #         title=f"发现未知的收件箱：{json.dumps(item)}",
                #         deadline=None,
                #         course_name="警告",
                #         url="about:blank",
                #         platform=cls.name,
                #     )
                # )
        return homeworks

    @classmethod
    async def valid_cookie(cls, cookie_dict: CookieTypes) -> bool:
        async with AsyncClient(cookies=cookie_dict) as client:
            return (await client.get(NOTICE_URL)).status_code == 200
