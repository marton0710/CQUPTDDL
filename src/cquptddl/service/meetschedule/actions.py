import uuid
from collections.abc import Iterable
from itertools import batched
from logging import INFO, getLogger

import meetschedule_sdk
from meetschedule_sdk import (
    AsyncMeetSchedule,
    Scope,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from cquptddl import core
from cquptddl.exc import (
    CquptddlException,
    InvalidMeetScheduleKey,
    MeetscheduleBindingExisted,
    MeetscheduleKeyPermissionDenied,
    MeetscheduleNotBound,
)
from cquptddl.model.db import Homework
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.db.meetschedule_tracked_event import (
    MeetscheduleEntry,
    MeetscheduleEntryStatus,
)

from . import limiter

_logger = getLogger(__name__)
_logger.setLevel(INFO)
_needed_meetschedule_key_permissions = {
    Scope.SCHEDULE_READ,
    Scope.ENTITIES_READ,
    Scope.ENTITIES_WRITE,
}


async def bind(session: AsyncSession, user_id: str, key: str):
    """绑定Meet课程表
    Raises:
        MeetscheduleBindingExisted: 该用户已经绑定过
        InvalidMeetscheduleKey: 非法的Meet课程表API密钥
        MeetscheduleKeyPermissionDenied: Meet课程表API密钥权限不够
    """
    # 不要重复绑定
    if await session.get(MeetscheduleConfig, user_id):
        raise MeetscheduleBindingExisted

    async with AsyncMeetSchedule(key) as meet, limiter.acquire(meet):
        # 检查key的权限
        try:
            async with limiter.acquire(meet, block=False):
                scopes = (await meet.key.get()).scopes
                if not all(p in scopes for p in _needed_meetschedule_key_permissions):
                    raise MeetscheduleKeyPermissionDenied
        except CquptddlException:
            raise
        except Exception as e:
            errno = uuid.uuid4()
            _logger.error("检查key权限时发生异常，错误码：%s", errno, exc_info=e)
            raise CquptddlException(
                f"检查key权限时发生异常，错误码：{errno}，请联系管理员"
            ) from e

        # 查询现在的schedule_id
        try:
            now_schedule = await meet.schedules.get_current()
        except meetschedule_sdk.exceptions.UnauthorizedError as e:
            raise InvalidMeetScheduleKey from e
        except meetschedule_sdk.ForbiddenError as e:
            raise MeetscheduleKeyPermissionDenied from e

    # 将绑定写入数据库
    config = MeetscheduleConfig(
        user_id=user_id,
        api_key=key,
        schedule_id=now_schedule.id,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)

    # 将当前用户的作业写入数据库
    sql = select(Homework.id).where(Homework.user_id == user_id)
    resp = await session.execute(sql)
    current_user_homework_ids = resp.scalars().all()
    ids_with_uid = ((hid, user_id) for hid in current_user_homework_ids)
    await add_new_homeworks_by_homework_ids(session, ids_with_uid)


async def unbind(session: AsyncSession, user_id: str):
    # 获取绑定信息
    config = await session.get(MeetscheduleConfig, user_id)
    if not config:
        raise MeetscheduleNotBound

    # 删除作业
    sql = select(MeetscheduleEntry).where(MeetscheduleEntry.user_id == user_id)
    resp = await session.execute(sql)
    entries = resp.scalars().all()
    await delete_homeworks_now(session, config, entries)

    # 删除meetschedule_tracked_event条目
    sql = delete(MeetscheduleConfig).where(MeetscheduleConfig.user_id == user_id)  # ty: ignore[invalid-argument-type]
    await session.execute(sql)


async def add_new_homeworks_by_homework_ids(
    session: AsyncSession, homework_and_user_ids: Iterable[tuple[uuid.UUID, str]]
):
    for hid, uid in homework_and_user_ids:
        session.add(
            MeetscheduleEntry(
                id=hid,
                meet_event_id=None,
                user_id=uid,
                status=MeetscheduleEntryStatus.PENDING,
            )
        )


async def add_new_homeworks_by_homeworks(
    session: AsyncSession, homeworks: Iterable[Homework]
):
    ids = ((h.id, h.user_id) for h in homeworks)
    await add_new_homeworks_by_homework_ids(session, ids)


async def update_homeworks_by_entries(entries: Iterable[MeetscheduleEntry]):
    for e in entries:
        e.status = MeetscheduleEntryStatus.PENDING_UPDATE


async def update_homeworks_by_homewok_ids(
    session: AsyncSession, homework_ids: Iterable[uuid.UUID]
):
    sql = select(MeetscheduleEntry).where(
        MeetscheduleEntry.id.in_(homework_ids)  # ty: ignore[unresolved-attribute]
    )
    resp = await session.execute(sql)
    entries = resp.scalars().all()
    await update_homeworks_by_entries(entries)


async def delete_homeworks_by_entries(entries: Iterable[MeetscheduleEntry]):
    for entry in entries:
        entry.status = MeetscheduleEntryStatus.PENDING_DELETE


async def delete_homeworks_by_homework_ids(
    session: AsyncSession, homework_ids: Iterable[uuid.UUID]
):
    sql = select(MeetscheduleEntry).where(
        MeetscheduleEntry.id.in_(homework_ids)  # ty: ignore[unresolved-attribute]
    )
    resp = await session.execute(sql)
    entries = resp.scalars().all()
    await delete_homeworks_by_entries(entries)


async def delete_homeworks_now(
    session: AsyncSession,
    config: MeetscheduleConfig,
    entries: Iterable[MeetscheduleEntry],
):
    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(config.api_key, client=client) as meet,
    ):
        for batch in batched(entries, 100):
            event_ids = [e.meet_event_id for e in batch if e.meet_event_id is not None]
            if event_ids:
                async with limiter.acquire(meet, block=False):
                    await meet.events.delete_batch(event_ids)

            # 删记录
            entry_ids = {e.id for e in batch}
            sql = delete(MeetscheduleEntry).where(MeetscheduleEntry.id.in_(entry_ids))  # ty: ignore[unresolved-attribute]
            await session.execute(sql)
