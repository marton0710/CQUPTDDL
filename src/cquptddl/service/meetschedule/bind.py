from contextlib import suppress

import meetschedule_sdk
from meetschedule_sdk import AsyncMeetSchedule
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete

from cquptddl import core
from cquptddl.exc import InvalidMeetScheduleKey, MeetscheduleBindingExisted
from cquptddl.model.db import User
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.schema.meetschedule import MeetscheduleConfigSchema

from . import limiter
from .actions import delete_events


async def bind(session: AsyncSession, user: User, model: MeetscheduleConfigSchema):
    if await session.get(MeetscheduleConfig, user.id):
        raise MeetscheduleBindingExisted

    # 查询现在的schedule_id
    async with AsyncMeetSchedule(model.meetschedule_key) as meet, limiter.acquire(meet):
        try:
            now_schedule = await meet.schedules.get_current()
        except meetschedule_sdk.exceptions.UnauthorizedError as e:
            raise InvalidMeetScheduleKey from e

    # 写入数据库
    session.add(
        MeetscheduleConfig(
            user_id=user.id,
            meetschedule_key=model.meetschedule_key,
            schedule_id=now_schedule.id,
        )
    )


async def unbind(user_id: str):
    async with core.factory.get_session() as session:
        # 发送请求，删除所有跟踪的事件
        with suppress(Exception):
            await delete_events(session, user_id)

        # 删除meetschedule_tracked_event条目
        sql = delete(MeetscheduleConfig).where(MeetscheduleConfig.user_id == user_id)  # ty: ignore[invalid-argument-type]
        await session.execute(sql)
