from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.adapter.platform.base import Platform as BasePlatform
from app.adapter.platform.yuketang.urls import BASE_URL
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

    async def get_homework(self) -> Homework:
        return Homework(
            title="雨课堂作业",
            content="雨课堂作业",
            url="",
            deadline=None,
            platform="雨课堂",
        )
