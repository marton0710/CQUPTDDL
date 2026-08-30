from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cquptddl import core
from cquptddl.model.db import Homework, User
from cquptddl.model.event import HomeworkRefreshedEvent
from cquptddl.model.schema.platform import PlatformEnum


async def refresh_homework(
    session: AsyncSession, user: User, platform_name: PlatformEnum
):
    """
    Raises:
        RefreshCoolingDown: 刷新作业还在冷却中
        PlatformNotBound: 用户未绑定该平台
    """

    # 获取所有作业
    homeworks = list[Homework](
        await core.symbol.call("platform.fetch_homework", session, user, platform_name)
    )

    # 落库并找出新增的作业id
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
    new_homework_ids = set[UUID]()
    for h in homeworks:
        if h.id not in stored_homework_ids:
            session.add(h)
            new_homework_ids.add(h.id)
        stored_homework_ids.discard(h.id)

    # 删除不存在的作业
    # await session.execute(
    #     delete(Homework).where(Homework.id.in_(stored_homework_ids))  # ty: ignore[unresolved-attribute, unused-ignore-comment]
    # )
    await session.commit()
    core.bus.emit(
        HomeworkRefreshedEvent(
            uid=user.id, platform_name=platform_name, new_homework_ids=new_homework_ids
        )
    )
