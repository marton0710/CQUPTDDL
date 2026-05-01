from abc import ABC, abstractmethod

from app.schemas.homework import Homework


class Platform(ABC):
    """作业平台抽象类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称，用于显示"""

    @abstractmethod
    async def get_homework(self) -> Homework:
        """获取作业"""
