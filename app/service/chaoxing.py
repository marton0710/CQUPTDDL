import httpx

from app.db.repositories import CookieRepositories
from app.db.session import SessonLocal
from app.utils import Error, encryptByAES


class ChaoXingService:
    """超星学习通服务层"""

    def __init__(self, username: str, password: str):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.platform = "学习通"
        self.login_url = "https://passport2.xuexitong.com/fanyalogin"
        self.notice_url = "https://notice.xuexitong.com/pc/notice/getNoticeList"
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=10,
        )
        self.username = username
        self.password = password

    async def get_chaoxing_cookie(self) -> dict:
        """
        获取超星cookie
        :return: 超星cookie
        """
        username = encryptByAES(self.username)
        password = encryptByAES(self.password)

        try:
            data = {
                "fid": -1,
                "uname": username,
                "password": password,
                "refer": "https%3A%2F%2Fi.xuexitong.com",
                "t": "true",
                "forbidotherlogin": 0,
                "validate": "",
                "doubleFactorLogin": 0,
                "independentId": 0,
                "independentNameId": 0,
            }
            resp = await self.client.post(
                url=self.login_url,
                data=data,
                follow_redirects=True,
            )
            resp.raise_for_status()
            result = resp.cookies
            if not result:
                raise Error(code=500, message="未获取cookie")

        except httpx.HTTPStatusError as e:
            raise Error(code=e.response.status_code, message=e.response.text)
        except httpx.TimeoutException as e:
            raise Error(code=500, message=f"请求超时：{e}")
        except httpx.RequestError as e:
            raise Error(code=500, message=f"请求错误：{e}")
        except Error:
            raise
        except Exception as e:
            raise Error(code=500, message=f"未知错误：{e}")

        return dict(result)

    async def get_chaoxing_activities(self):
        """
        获取通知列表里的作业
        :return:
        """
        homework: dict[str, str] = {}
        try:
            resp = await self.client.get(url=self.notice_url)
            resp.raise_for_status()
            payload = resp.json()

            notices_list = payload.get("notices", {}).get("list", [])
            for item in notices_list:
                title = item.get("title")
                creater_name = item.get("createrName")
                if creater_name == "学习通知" and title[:3] == "作业:":
                    content = item.get("content")
                    homework[title] = content
            return homework
        except Error:
            raise
        except httpx.HTTPStatusError as e:
            raise Error(code=500, message=f"HTTP错误：{e}")
        except Exception as e:
            raise Error(code=500, message=f"获取作业错误：{e}")

    async def close(self):
        """
        关闭client
        :return:
        """
        await self.client.aclose()
