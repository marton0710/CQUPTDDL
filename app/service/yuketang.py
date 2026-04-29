import httpx
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import CookieRepositories
from app.utils import Error
from app.utils import shifttime


class YuKeTangService:
    """长江雨课堂服务层"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CookieRepositories(session=session)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.platform = "雨课堂"
        self.client = None
        self.base_url = "https://changjiang.yuketang.cn"

    @classmethod
    async def create(cls, session: AsyncSession):
        """
        初始化
        :param session: 数据库会话
        :return:
        """
        self = cls(session=session)
        cookies = await self._get_cookie_from_db()
        if not await self._valid_cookie(cookie_dict=cookies):
            cookies = await self._get_yuketang_cookie()
            await self.save_cookie_to_db(cookie_dict=cookies)
        self.client = httpx.AsyncClient(
            headers=self.headers,
            cookies=cookies,
            timeout=10,
        )
        return self

    async def _get_yuketang_cookie(self) -> dict[str, str]:
        """
        获取雨课堂cookie
        :return:
        """
        try:
            async with async_playwright() as p:
                browser = await p.webkit.launch(headless=False)
                context = await browser.new_context(user_agent=self.headers["User-Agent"])
                page = await context.new_page()
                await page.goto(self.base_url, wait_until="domcontentloaded")
                await page.wait_for_selector("text=我听的课", timeout=90000)
                raw_cookie = await context.cookies()
                await browser.close()

            cookie_dict = {item["name"]: item["value"] for item in raw_cookie}
            return cookie_dict
        except PlaywrightTimeoutError:
            raise Error(code=500, message="雨课堂登录超时")
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"保存雨课堂登录态失败: {e}")

    async def _get_cookie_from_db(self) -> dict[str, str]:
        """
        从数据库获取
        :return:
        """
        row = await self.repo.get_cookie(platform=self.platform)
        if not row:
            cookies = await self._get_yuketang_cookie()
            await self.repo.create_cookie(
                platform=self.platform,
                cookies=cookies,
            )
            await self.session.commit()
            return cookies
        return row.cookies

    async def save_cookie_to_db(self, cookie_dict: dict[str, str]) -> None:
        """
        保存新的cookie
        :return:
        """
        await self.repo.update_cookie(
            platform=self.platform,
            cookies=cookie_dict,
        )
        await self.session.commit()

    async def _valid_cookie(self, cookie_dict) -> bool:
        """
        验证cookie的合理性
        :return:
        """
        url = f"{self.base_url}/v2/api/web/courses/list?identity=2"
        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                cookies=cookie_dict,
                timeout=10,
            ) as client:
                resp = await client.get(url=url, cookies=cookie_dict)
                resp.raise_for_status()
                payload = resp.json()
                return payload.get("errcode") == 0
        except httpx.HTTPError as e:
            raise Error(code=500, message=f"校验雨课堂 cookie 失败：{e}")

    async def _get_course(self) -> dict[str, int]:
        """
        获取课程列表
        :return:
        """
        dist_url = f"{self.base_url}/v2/api/web/courses/list?identity=2"
        class_info: dict[str, int] = {}
        try:
            resp = await self.client.get(url=dist_url)
            resp.raise_for_status()
            payload = resp.json()

            course_list = payload.get("data", {}).get("list", [])
            for item in course_list:
                name = item.get("name")
                classroom_id = item.get("classroom_id")
                if name and classroom_id is not None:
                    class_info[str(name)] = int(classroom_id)
            return class_info
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"获取课程列表失败：{e}")

    async def _get_course_activities(self, classroom_id: int):
        """
        获取单个课程的列表
        :return:
        """
        dist_url = (
            f"{self.base_url}/v2/api/web/logs/learn/"
            f"{classroom_id}?actype=-1&page=0&offset=20&sort=-1"
        )
        homework = {}
        try:
            resp = await self.client.get(url=dist_url)
            resp.raise_for_status()
            payload = resp.json()
            for item in payload.get("data", {}).get("activities", []):
                if item.get("type") == 5:
                    title = item.get("title")
                    begin_time = shifttime(int(item.get("create_time")))
                    end_time = shifttime(int(item.get("deadline")))
                    homework[title] = [begin_time, end_time]
                elif item.get("type") == 20:
                    title = item.get("title")
                    begin_time = shifttime(int(item.get("create_time")))
                    end_time = shifttime(int(item.get("content", {}).get("score_d")))
                    homework[title] = [begin_time, end_time]
            return homework
        except Error:
            raise
        except httpx.HTTPError as e:
            raise Error(code=500, message=f"请求课程活动失败: {e}")

    async def get_yuketang_homework(self) -> dict[str, dict[str, list]]:
        """
        获取雨课堂作业
        :return:
        """
        courses: dict[str, int] = await self._get_course()
        if not courses:
            return {}
        # 信号量限制并发数
        semaphore = asyncio.Semaphore(3)

        async def fetch_one_course(
                course_name: str,
                classroom_id: int,
        ) -> tuple[str, dict[str, list[str]]]:
            # 最多5个在爬取
            async with semaphore:
                try:
                    homework = await self._get_course_activities(classroom_id=classroom_id)
                    return course_name, homework
                except Error as e:
                    return course_name, {
                        "__error__": [f"获取失败：{e.message}", ""],
                    }
                except Exception as e:
                    return course_name, {
                        "__error__": [f"获取失败：{e}", ""],
                    }

        # 创建任务列表
        tasks = [
            fetch_one_course(course_name=course_name, classroom_id=classroom_id)
            for course_name, classroom_id in courses.items()
        ]
        results = await asyncio.gather(*tasks)

        return {
            course_name: homework
            for course_name, homework in results
        }

    async def close(self):
        """
        关闭client
        :return:
        """
        if self.client is not None:
            await self.client.aclose()
