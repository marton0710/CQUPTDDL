import asyncio
from datetime import datetime

import httpx
from fuckids.context import Context
from fuckids.errors import DataRequired
from fuckids.workflow import password_login_workflow
from httpx import AsyncClient, Client

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.xuezai.urls import LOGIN_ENTRYPOINT_URL, TODO_URL
from app.schemas.homework import Homework
from app.utils.error import Error, LoginFailed


class Xuezai(BasePlatform):
    @property
    def name(self) -> str:
        return "学在重邮"

    @staticmethod
    async def login(client: AsyncClient, username: str, password: str):
        resp = await client.get(LOGIN_ENTRYPOINT_URL, follow_redirects=True)
        sync_client = Client(cookies=client.cookies, verify=False)
        ctx = Context(
            service=str(resp.url),
            username=username,
            password=password,
            client=sync_client.cookies,  # type: ignore
        )
        while True:
            try:
                redirect_url = await asyncio.to_thread(password_login_workflow.run, ctx)
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

        client.cookies.update(ctx.client.cookies)
        resp = await client.get(redirect_url, follow_redirects=True)

    @staticmethod
    async def get_homework(client: AsyncClient):
        try:
            resp = await client.get(TODO_URL)
            resp.raise_for_status()
            payload: dict = resp.json()["todo_list"]
            return [
                Homework(
                    course_name=item["course_name"],
                    title=item["title"],
                    content=item["title"],
                    url="about:blank",
                    deadline=datetime.fromisoformat(item["end_time"]),
                    platform="学在重邮",
                )
                for item in payload
            ]
        except httpx.HTTPStatusError as e:
            raise Error(
                code=e.response.status_code, message=f"获取todo列表失败：{e}"
            ) from e
