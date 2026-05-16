from datetime import datetime

import httpx
from fuckids.context import AsyncContext
from fuckids.errors import DataRequired
from fuckids.workflow import password_login_workflow_async
from httpx import AsyncClient
from httpx._types import CookieTypes

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.yuketang.urls import (
    GET_COURSE_HOMEWORK_URL,
    GET_COURSES_URL,
    HOMEWORK_DETAIL_URL,
    IDSLOGIN_SERVICE_URL,
)
from app.schemas.homework import Homework
from app.utils.error import LoginFailed

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"


class Yuketang(BasePlatform):
    @property
    def name(_) -> str:
        return "雨课堂"

    @staticmethod
    async def login(client: AsyncClient, username: str, password: str):
        ctx = AsyncContext(
            client=client,
            service=IDSLOGIN_SERVICE_URL,
            username=username,
            password=password,
        )
        while True:
            try:
                redirect_url = await password_login_workflow_async.run(ctx)
            except DataRequired as e:
                for k in e.keys:
                    match k:
                        case "captcha":
                            raise LoginFailed(
                                "需要验证码。请先去统一认证平台登录一次，以去除验证码"
                            )
                        case "kick_existing_session":
                            ctx.kick_existing_session = True
                        case _:
                            raise LoginFailed(f"缺少参数： {k}")
            else:
                break

        await client.get(redirect_url, follow_redirects=True)
        sessionid = client.cookies["sessionid"]
        del client.cookies["sessionid"]
        client.cookies["sessionid"] = sessionid

    @staticmethod
    async def get_homework(client: AsyncClient) -> list[Homework]:
        courses = await Yuketang._get_course(client)
        homeworks = []
        for cn, cid in courses.items():
            homeworks.extend(await Yuketang._get_course_homeworks(client, cn, cid))
        return homeworks

    @staticmethod
    async def valid_cookie(cookie_dict: CookieTypes) -> bool:
        """
        验证cookie的合理性
        :return:
        """
        url = GET_COURSES_URL
        async with httpx.AsyncClient(
            headers={"User-Agent": UA},
            cookies=cookie_dict,
            timeout=10,
        ) as client:
            return (await client.get(url=url, cookies=cookie_dict)).status_code == 200

    @staticmethod
    async def _get_course(client: AsyncClient) -> dict[str, int]:
        """
        获取课程列表
        :return:
        """
        dist_url = GET_COURSES_URL
        class_info: dict[str, int] = {}
        payload = (await client.get(url=dist_url)).raise_for_status().json()

        course_list = payload.get("data", {}).get("list", [])
        for item in course_list:
            name = item.get("name")
            classroom_id = item.get("classroom_id")
            if name and classroom_id is not None:
                class_info[str(name)] = int(classroom_id)
        return class_info

    @staticmethod
    async def _get_course_homeworks(
        client: AsyncClient, course_name: str, classroom_id: int
    ):
        payload = (
            (
                await client.get(
                    GET_COURSE_HOMEWORK_URL.format(classroom_id=classroom_id)
                )
            )
            .raise_for_status()
            .json()
        )
        homeworks: list[Homework] = []
        for item in payload.get("data", {}).get("activities", []):
            if item.get("type") == 5:
                ddl_timestamp = item["deadline"] // 1000
                homeworks.append(
                    Homework(
                        course_name=course_name,
                        title=item["title"],
                        deadline=datetime.fromtimestamp(ddl_timestamp)
                        if ddl_timestamp != 0
                        else None,
                        url=HOMEWORK_DETAIL_URL.format(
                            classroom_id=classroom_id, hmw_id=item["courseware_id"]
                        ),
                        platform="雨课堂",
                    )
                )
            elif item.get("type") == 20:
                ddl_timestamp = item["content"]["score_d"] // 1000
                homeworks.append(
                    Homework(
                        course_name=course_name,
                        title=item["title"],
                        deadline=datetime.fromtimestamp(ddl_timestamp)
                        if ddl_timestamp != 0
                        else None,
                        url=HOMEWORK_DETAIL_URL.format(
                            classroom_id=classroom_id,
                            hmw_id=item["content"]["leaf_type_id"],
                        ),
                        platform="雨课堂",
                    )
                )

        return homeworks
