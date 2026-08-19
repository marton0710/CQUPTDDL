import json
from datetime import datetime
from logging import INFO, getLogger

from httpx import AsyncClient, HTTPStatusError

from cquptddl import core
from cquptddl.exc import InvalidPlatformCookie, LoginFailed
from cquptddl.model.db import User
from cquptddl.model.db.homework import Homework
from cquptddl.model.schema.platform import (
    AuthMethod,
    PasswordLoginInput,
    PlatformEnum,
)
from cquptddl.service.platform.base import Platform as BasePlatform

from .urls import LOGIN_URL, NOTICE_URL
from .utils import encryptByAES

_logger = getLogger(__name__)
_logger.setLevel(INFO)
_logger_for_unknown_inbox = getLogger(__name__ + ":unknown-inbox")


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
    async def get_homework(cls, cookies: dict[str, str], user: User) -> list[Homework]:
        async with core.factory.get_client(cookies=cookies) as client:
            try:
                data = (
                    (await client.get(NOTICE_URL))
                    .raise_for_status()
                    .json()["notices"]["list"]
                )
            except HTTPStatusError as e:
                exc = InvalidPlatformCookie()
                _logger.error("学习通cookie无效", exc_info=exc)
                raise exc from e
        homeworks: list[Homework] = []
        for item in data:
            try:
                msg_info = json.loads(item["extendParam"]["cparams"])["funConfig"]
                if msg_info["funTag"] != 3:
                    continue

                hmw_info = msg_info["content"]
                _logger.debug("作业详情：%s", hmw_info)
                hmw_url = json.loads(item["attachment"])[0]["att_web"]["url"]
            except Exception as e:  # noqa: BLE001
                _logger_for_unknown_inbox.warning(
                    "发现未知的收件箱：%s", json.dumps(item)
                )
                _logger_for_unknown_inbox.debug("详细报错如下：", exc_info=e)
                continue
            homeworks.append(
                Homework(
                    id=Homework.generate_id(
                        user.id, cls.name, hmw_info["courseName"], hmw_info["title"]
                    ),
                    user_id=user.id,
                    title=hmw_info["title"],
                    deadline=datetime.fromtimestamp(
                        int(hmw_info["endTime"]) / 1000
                    ).astimezone()
                    if hmw_info["endTime"]
                    else None,
                    course_name=hmw_info["courseName"],
                    url=hmw_url,
                    platform=cls.name,
                )
            )
        return homeworks

    @classmethod
    async def valid_cookie(cls, cookies: dict[str, str]) -> bool:
        async with core.factory.get_client(cookies=cookies) as client:
            return (await client.get(NOTICE_URL)).status_code == 200
