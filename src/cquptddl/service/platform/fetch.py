import asyncio
from collections.abc import Iterable
from datetime import datetime, timedelta
from logging import INFO, getLogger

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import InvalidPlatformCookie, PlatformNotBound, RefreshCoolingDown
from cquptddl.model.db import Homework, PlatformInfo, User
from cquptddl.model.schema.platform import PlatformEnum

from . import auth
from .base import Platform

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def fetch_homework(
    session: AsyncSession,
    user: User,
    platform_name: PlatformEnum,
    check_cooldown: bool = True,
) -> Iterable[Homework]:
    """
    Raises:
        PlatformNotBound: 用户没有绑定该平台
        InvalidPlatformCookie: 平台cookie无效
    """
    platform_info = await session.get(PlatformInfo, (user.id, platform_name))
    if platform_info is None:
        raise PlatformNotBound
    if check_cooldown:
        _check_platform_cooldown(platform_info)
    platform = Platform.get_platform_by_name(platform_name)
    for attempt_time in range(core.config.homework_refresh_attempts):
        try:
            homeworks = await platform.get_homework(platform_info.cookies, user)
        except InvalidPlatformCookie:
            if attempt_time >= core.config.homework_refresh_attempts - 1:
                raise
            _logger.debug(
                "用户%s在平台%s的token已过期，正在重新登录(%s/%s)",
                user.id,
                platform_name,
                attempt_time + 1,
                core.config.homework_refresh_attempts - 1,
            )
            await auth.relogin(session, user, platform_name)
        except httpx.TimeoutException:
            if attempt_time >= core.config.homework_refresh_attempts - 1:
                raise
            _logger.warning(
                "用户%s刷新平台%s作业时发生超时，正在重试(%s/%s)",
                user.id,
                platform_name,
                attempt_time + 1,
                core.config.homework_refresh_attempts - 1,
            )
            await asyncio.sleep(1)
        else:
            break
    return homeworks


def _check_platform_cooldown(platform_info: PlatformInfo):
    now = datetime.now()  # noqa: DTZ005
    if now - platform_info.last_refreshed_homework < timedelta(
        seconds=core.config.homework_cooldown_ttl
    ):
        raise RefreshCoolingDown
    platform_info.last_refreshed_homework = now
