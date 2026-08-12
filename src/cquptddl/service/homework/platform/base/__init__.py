from abc import ABC, abstractmethod
from collections.abc import Iterable
from logging import INFO, getLogger
from typing import ClassVar

from httpx import AsyncClient
from httpx._types import CookieTypes

from cquptddl.model.db import User
from cquptddl.model.db.homework import Homework
from cquptddl.model.schema.platform_auth import AllAuthInputs, AuthMethod, PlatformEnum

logger = getLogger(__name__)
logger.setLevel(INFO)


class Platform(ABC):
    """作业平台抽象类"""

    name: PlatformEnum
    """平台名称，用于显示"""
    auth_method: AuthMethod
    """认证方式"""

    _platforms: ClassVar[dict[PlatformEnum, type[Platform]]] = {}
    """目前注册的所有平台"""

    @classmethod
    @abstractmethod
    async def login(
        cls, client: AsyncClient, user: User, credentials: AllAuthInputs
    ) -> dict[str, str]:
        """平台登录
        Returns:
            cookies: 一般是最小token，因平台而异
        """

    @classmethod
    @abstractmethod
    async def get_homework(
        cls, cookies: dict[str, str], user: User
    ) -> Iterable[Homework]:
        """获取作业
        Raises:
            InvalidPlatformCookie: 平台cookie无效
        """

    @classmethod
    @abstractmethod
    async def valid_cookie(cls, cookie_dict: CookieTypes) -> bool:
        """检查cookie是否有效"""

    @classmethod
    def get_platform_by_name(cls, name: PlatformEnum) -> type[Platform]:
        return cls._platforms[name]

    def __init_subclass__(cls, **k):
        super().__init_subclass__(**k)
        if not hasattr(cls, "name") or not hasattr(cls, "auth_method"):
            raise SyntaxError(f"子类{cls}未定义要求的字段")
        cls._platforms[cls.name] = cls
