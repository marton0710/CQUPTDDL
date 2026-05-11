from datetime import datetime

import httpx
from fuckids.context import AsyncContext
from fuckids.errors import DataRequired
from fuckids.workflow import password_login_workflow_async
from httpx import AsyncClient, Client
from httpx._types import CookieTypes

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.xuezai.urls import (
    HOMEWORK_DETAIL_URL,
    LOGIN_ENTRYPOINT_URL,
    TODO_URL,
)
from app.schemas.homework import Homework
from app.utils.error import Error, LoginFailed


class Xuezai(BasePlatform):
    @property
    def name(self) -> str:
        return "学在重邮"

    @staticmethod
    async def login(client: AsyncClient, username: str, password: str):
        resp = await client.get(LOGIN_ENTRYPOINT_URL, follow_redirects=True)
        ctx = AsyncContext(
            service=str(resp.url), username=username, password=password, client=client
        )
        while True:
            try:
                redirect_url = await password_login_workflow_async.run(ctx)
            except DataRequired as e:
                for k in e.keys:
                    if k == "captcha":
                        raise LoginFailed(
                            "需要验证码。请先去统一认证平台登录一次，以去除验证码"
                        ) from e
                    elif k == "kick_existing_session":
                        ctx.kick_existing_session = True
                    else:
                        raise LoginFailed(f"缺少数据：{e}") from e
            else:
                break

        client = ctx.client
        resp = await client.get(redirect_url, follow_redirects=True)

    @staticmethod
    async def get_homework(client: AsyncClient) -> list[Homework]:
        try:
            resp = await client.get(TODO_URL)
            resp.raise_for_status()
            payload: dict = resp.json()["todo_list"]
            return [
                Homework(
                    course_name=item["course_name"],
                    title=item["title"],
                    url=HOMEWORK_DETAIL_URL.format(
                        course_id=item["course_id"], hmw_id=item["id"]
                    ),
                    deadline=datetime.fromisoformat(item["end_time"]),
                    platform="学在重邮",
                )
                for item in payload
            ]
        except httpx.HTTPStatusError as e:
            raise Error(
                code=e.response.status_code, message=f"获取todo列表失败：{e}"
            ) from e

    @staticmethod
    async def valid_cookie(cookie_dict: CookieTypes) -> bool:
        async with httpx.AsyncClient(cookies=cookie_dict) as client:
            return (await client.get(TODO_URL)).status_code == 200
