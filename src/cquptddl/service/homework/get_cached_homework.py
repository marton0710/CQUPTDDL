from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cquptddl.model.db import Homework, LastRefreshTime, User
from cquptddl.model.schema.platform_auth import PlatformEnum


async def get_cached_homework(
    session: AsyncSession,
    user: User,
    platform_name: PlatformEnum | None = None,
    num: int = -1,
    page: int = 1,
) -> Iterable[Homework]:
    stmt = select(Homework).where(Homework.user_id == user.id).order_by(Homework.id)  # ty: ignore[invalid-argument-type]
    if platform_name is not None:
        stmt = stmt.where(Homework.platform == platform_name)
    if num >= 0:
        stmt = stmt.limit(num).offset((page - 1) * num)
    resp = await session.execute(stmt)
    return resp.scalars().all()


async def get_cached_homework_count(
    session: AsyncSession, user: User, platform_name: PlatformEnum | None = None
) -> int:
    stmt = select(func.count()).where(Homework.user_id == user.id)
    if platform_name is not None:
        stmt = stmt.where(Homework.platform == platform_name)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def get_last_refresh_time(
    session: AsyncSession, user: User, platform_name: PlatformEnum | None = None
) -> datetime:
    stmt = select(func.max(LastRefreshTime.last_refreshed_homework)).where(
        LastRefreshTime.user_id == user.id
    )  # XXX: max还是min还是什么存在争议，因为作业不一定是同时刷新
    if platform_name is not None:
        stmt = stmt.where(LastRefreshTime.platform == platform_name)
    resp = await session.execute(stmt)
    return resp.scalar_one() or datetime.fromtimestamp(0).astimezone()
