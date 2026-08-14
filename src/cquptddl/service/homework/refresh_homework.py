from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from cquptddl import core
from cquptddl.model.db import Homework, User
from cquptddl.model.event import HomeworkRefreshedEvent
from cquptddl.model.schema.platform_auth import PlatformEnum


async def refresh_homework(
    session: AsyncSession, user: User, platform_name: PlatformEnum
):
    """
    Raises:
        RefreshCoolingDown: 刷新作业还在冷却中
        PlatformNotBound: 用户未绑定该平台
    """

    # 获取所有作业
    homeworks = list(
        await core.symbol.call("platform.fetch_homework", session, user, platform_name)
    )

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
    core.bus.emit(HomeworkRefreshedEvent(uid=user.id, platform_name=platform_name))
