import httpx
from bs4 import BeautifulSoup
from httpx import URL

from app.db.repositories import CookieRepositories
from app.utils import Error, LoginAES


class XueZaiService:
    """学在重邮服务层"""

    def __init__(self, username: str, password: str):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=10,
        )
        self.platform = "学在重邮"
        self.todo_url = "http://lms.tc.cqupt.edu.cn/api/todos"
        self.username = username
        self.login_url = None
        self.key = None
        self.execution = None
        self.raw_password = password
        self.password = None

    @classmethod
    async def create(cls, username: str, password: str):
        """
        创建对象初始化
        :param username: 用户名
        :param password: 密码
        :return: self对象
        """
        self = cls(username=username, password=password)
        self.login_url = str(await self._get_login_url())
        self.key, self.execution = await self._get_salt_execution()
        self.password = LoginAES(password=self.raw_password, salt=self.key).encrypt_password()
        return self

    async def _get_login_url(self) -> URL:
        """
        ids网址
        :return:
        """
        resp = await self.client.get(url="http://lms.tc.cqupt.edu.cn", follow_redirects=True)
        return resp.url

    async def _get_salt_execution(self):
        """
        获取密钥key和execution
        :return: key和execution
        """
        resp = await self.client.get(url=self.login_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        key = soup.find("input", attrs={"id": "pwdEncryptSalt"})["value"]
        execution = soup.find("input", attrs={"id": "execution"})["value"]

        return key, execution

    async def get_xuezai_cookie(self):
        """
        获取学在重邮cookie
        :return:
        """
        data = {
            "username": self.username,
            "password": self.password,
            "captcha": "",
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": self.execution,
        }
        resp = await self.client.post(url=self.login_url, follow_redirects=True, data=data)
        return resp.cookies

    async def get_xuezai_todo(self):
        try:
            resp = await self.client.get(url=self.todo_url)
            resp.raise_for_status()
            payload = resp.json()
            return payload
        except httpx.HTTPStatusError as e:
            raise Error(code=e.response.status_code, message=f"获取todo列表失败：{e}")

    async def close(self):
        """
        关闭client
        :return:
        """
        await self.client.aclose()
