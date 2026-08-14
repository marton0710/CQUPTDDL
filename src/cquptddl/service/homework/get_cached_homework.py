from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from cquptddl import core
from cquptddl.core import get_session
from cquptddl.model.db import Homework, User
from cquptddl.model.db.platform_info import PlatformInfo
from cquptddl.model.event import PlatformUnboundEvent
from cquptddl.model.schema.platform_auth import PlatformEnum


async def get_cached_homework(
    session: AsyncSession,
    user: User,
    platform_name: PlatformEnum | None = None,
    num: int = -1,
    page: int = 1,
) -> Iterable[Homework]:
    stmt = (
        select(Homework).where(Homework.user_id == user.id).order_by(Homework.deadline)  # ty: ignore[invalid-argument-type]
    )
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
    stmt = select(func.max(PlatformInfo.last_refreshed_homework)).where(
        PlatformInfo.user_id == user.id
    )  # XXX: max还是min还是什么存在争议，因为作业不一定是同时刷新
    if platform_name is not None:
        stmt = stmt.where(PlatformInfo.platform == platform_name)
    resp = await session.execute(stmt)
    return resp.scalar_one() or datetime.fromtimestamp(0).astimezone()


async def delete_platform_homework_event_callback(e: PlatformUnboundEvent):
    async with get_session() as session:
        await delete_platform_homework(session, e.uid, e.platform_name)


async def delete_platform_homework(
    session: AsyncSession, uid: str, platform_name: PlatformEnum
):
    stmt = (
        delete(Homework)
        .where(Homework.user_id == uid)  # ty: ignore[invalid-argument-type]
        .where(Homework.platform == platform_name)  # ty: ignore[invalid-argument-type]
    )
    await session.execute(stmt)


core.bus.on(PlatformUnboundEvent, delete_platform_homework_event_callback)
