from abc import ABC, abstractmethod
from typing import Iterable

from httpx import AsyncClient

from app.schemas.homework import Homework


class Platform(ABC):
    """作业平台抽象类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称，用于显示"""

    @staticmethod
    @abstractmethod
    async def get_homework(client: AsyncClient) -> Iterable[Homework]:
        """获取作业"""
