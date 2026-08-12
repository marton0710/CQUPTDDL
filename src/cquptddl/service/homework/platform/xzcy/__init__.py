from datetime import datetime
from logging import INFO, getLogger
from urllib.parse import parse_qs

import httpx
from httpx import AsyncClient, HTTPStatusError
from httpx._types import CookieTypes

from cquptddl.exc import CquptddlException, InvalidPlatformCookie, LoginFailed
from cquptddl.model.db.homework import Homework
from cquptddl.model.db.user import User
from cquptddl.model.schema.platform_auth import AuthMethod, IDSLoginInput, PlatformEnum
from cquptddl.service.homework.platform.base import Platform as BasePlatform
from cquptddl.service.homework.platform.base.utils import login_from_platform_account

from .urls import (
    HOMEWORK_DETAIL_URL,
    LOGIN_ENTRYPOINT_URL,
    TODO_URL,
)

logger = getLogger(__name__)
logger.setLevel(INFO)


class Xzcy(BasePlatform):
    name = PlatformEnum.XZCY
    auth_method = AuthMethod.CQUPT_IDS

    @classmethod
    async def login(
        cls, client: AsyncClient, user: User, credentials: IDSLoginInput
    ) -> dict[str, str]:  # ty: ignore[invalid-method-override]
        """
        Raises: cquptddl.exc.LoginFailed"""
        resp = await client.get(LOGIN_ENTRYPOINT_URL, follow_redirects=True)
        service = parse_qs(resp.url.query.decode())["service"][0]

        redirect_url = await login_from_platform_account(user, service)
        resp = await client.get(redirect_url, follow_redirects=True)
        if resp.url.path != "/user/index":
            raise LoginFailed("学在重邮登录失败")

        return dict(client.cookies)

    @classmethod
    async def get_homework(cls, client: AsyncClient, user: User) -> list[Homework]:
        try:
            resp = await client.get(TODO_URL)
            try:
                resp.raise_for_status()
            except HTTPStatusError as e:
                exc = InvalidPlatformCookie()
                logger.error("学在重邮cookie无效", exc_info=exc)
                raise exc from e
            payload: dict = resp.json()["todo_list"]
            return [
                Homework(
                    id=Homework.generate_id(
                        user.id, cls.name, item["course_name"], item["title"]
                    ),
                    user_id=user.id,
                    course_name=item["course_name"],
                    title=item["title"],
                    url=HOMEWORK_DETAIL_URL.format(
                        course_id=item["course_id"], hmw_id=item["id"]
                    ),
                    deadline=datetime.fromisoformat(item["end_time"]),
                    platform=cls.name,
                )
                for item in payload
            ]
        except httpx.HTTPStatusError as e:
            raise CquptddlException(f"获取todo列表失败：{e}") from e

    @classmethod
    async def valid_cookie(cls, cookie_dict: CookieTypes) -> bool:
        async with httpx.AsyncClient(cookies=cookie_dict) as client:
            return (await client.get(TODO_URL)).status_code == 200
