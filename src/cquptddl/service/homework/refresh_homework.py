from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from cquptddl.core import config
from cquptddl.exc import PlatformNotBound, RefreshCoolingDown
from cquptddl.model.db import Homework, User
from cquptddl.model.db.platform_info import PlatformInfo
from cquptddl.model.schema.platform_auth import PlatformEnum

from . import platform


async def refresh_homework(
    session: AsyncSession, user: User, platform_name: PlatformEnum
):
    """
    Raises:
        RefreshCoolingDown: 刷新作业还在冷却中
        PlatformNotBound: 用户未绑定该平台
    """
    await _check_platform_fetch_cool_down(user, session, platform_name)

    # 获取所有作业
    homeworks = list(await platform.fetch_homework(session, user, platform_name))

    # 落库
    stored_homework_ids = set(
        (
            await session.execute(
                select(Homework.id)
                .where(Homework.user_id == user.id)
                .where(Homework.platform == platform_name)
            )
        )
        .scalars()
        .all()
    )
    for h in homeworks:
        if h.id not in stored_homework_ids:
            session.add(h)
        stored_homework_ids.discard(h.id)

    # 删除不存在的作业
    await session.execute(
        delete(Homework).where(Homework.id.in_(stored_homework_ids))  # ty: ignore[unresolved-attribute]
    )


async def _check_platform_fetch_cool_down(
    user: User, session: AsyncSession, platform_name: PlatformEnum
):
    """
    Raises:
        PlatformNotBound:
        RefreshCoolingDown:
    """
    now = datetime.now()  # ruff: ignore[DTZ005]
    if (
        platform_info_obj := await session.get(PlatformInfo, (user.id, platform_name))
    ) is None:
        raise PlatformNotBound
    if now - platform_info_obj.last_refreshed_homework < timedelta(
        seconds=config.homework_cooldown_ttl
    ):
        raise RefreshCoolingDown
    platform_info_obj.last_refreshed_homework = now
