from abc import ABC, abstractmethod
from typing import Iterable

from httpx import AsyncClient
from httpx._types import CookieTypes

from app.schemas.homework import Homework


class Platform(ABC):
    """作业平台抽象类"""

    @property
    @abstractmethod
    def name(_) -> str:
        """平台名称，用于显示"""

    @staticmethod
    @abstractmethod
    async def get_homework(client: AsyncClient) -> Iterable[Homework]:
        """获取作业"""

    @staticmethod
    @abstractmethod
    async def valid_cookie(cookie_dict: CookieTypes) -> bool:
        """检查cookie是否有效"""
