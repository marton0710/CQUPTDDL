from datetime import datetime

import httpx
from httpx import AsyncClient
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.yuketang.urls import (
    BASE_URL,
    GET_COURSE_HOMEWORK_URL,
    GET_COURSES_URL,
)
from app.schemas.homework import Homework
from app.utils.error import Error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"


class Yuketang(BasePlatform):
    @property
    def name(self) -> str:
        return "雨课堂"

    @staticmethod
    async def login() -> dict[str, str]:
        try:
            async with async_playwright() as p:
                browser = await p.webkit.launch(headless=False)
                context = await browser.new_context(user_agent=UA)
                page = await context.new_page()
                await page.goto(BASE_URL, wait_until="domcontentloaded")
                await page.wait_for_selector("text=我听的课", timeout=90000)
                raw_cookie = await context.cookies()
                await browser.close()

            cookie_dict = {item["name"]: item["value"] for item in raw_cookie}  # type: ignore
            return cookie_dict
        except PlaywrightTimeoutError as e:
            raise Error(code=500, message="雨课堂登录超时") from e
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"保存雨课堂登录态失败: {e}") from e

    @staticmethod
    async def get_homework(client: AsyncClient) -> list[Homework]:
        courses = await Yuketang._get_course(client)
        homeworks = []
        for cn, cid in courses.items():
            homeworks.extend(await Yuketang._get_course_homeworks(client, cn, cid))
        return homeworks

    @staticmethod
    async def valid_cookie(cookie_dict: dict[str, str]) -> bool:
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
            resp = await client.get(url=url, cookies=cookie_dict)
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("errcode") == 0

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
        url = (GET_COURSE_HOMEWORK_URL / str(classroom_id)).url
        payload = (await client.get(url=url)).raise_for_status().json()
        homeworks: list[Homework] = []
        for item in payload.get("data", {}).get("activities", []):
            if item.get("type") == 5:
                ddl_timestamp = item["deadline"] // 1000
                homeworks.append(
                    Homework(
                        course_name=course_name,
                        title=item["title"],
                        content=item["title"],
                        deadline=datetime.fromtimestamp(ddl_timestamp)
                        if ddl_timestamp != 0
                        else None,
                        url="about:blank",
                        platform="雨课堂",
                    )
                )
            elif item.get("type") == 20:
                ddl_timestamp = item["content"]["score_d"] // 1000
                homeworks.append(
                    Homework(
                        course_name=course_name,
                        title=item["title"],
                        content=item["title"],
                        deadline=datetime.fromtimestamp(ddl_timestamp)
                        if ddl_timestamp != 0
                        else None,
                        url="about:blank",
                        platform="雨课堂",
                    )
                )
        return homeworks
