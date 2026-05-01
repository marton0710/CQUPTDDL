import asyncio
from datetime import datetime

from fuckids.context import Context
from fuckids.errors import DataRequired
from fuckids.workflow import password_login_workflow
from httpx import AsyncClient, Request

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.xuezai.urls import LOGIN_ENTRYPOINT_URL
from app.schemas.homework import Homework
from app.utils.error import LoginFailed


class Xuezai(BasePlatform):
    @property
    def name(self) -> str:
        return "学在重邮"

    @staticmethod
    async def login(client: AsyncClient, username: str, password: str):
        req = Request("GET", LOGIN_ENTRYPOINT_URL)
        for _ in range(2):
            req = (await client.send(req)).next_request
            assert req

        ctx = Context(service=str(req.url), username=username, password=password)
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

        await client.get(redirect_url, follow_redirects=True)

    async def get_homework(self) -> Homework:
        return Homework(
            title="学在重邮",
            content="学在重邮",
            deadline=datetime.now(),
            url="",
            platform="学在重邮",
        )
