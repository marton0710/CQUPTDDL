from collections import defaultdict
from collections.abc import Iterable
from contextlib import asynccontextmanager
from itertools import batched
from logging import INFO, getLogger
from uuid import UUID

import meetschedule_sdk
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from meetschedule_sdk import (
    AsyncMeetSchedule,
    EventInput,
    EventPatch,
    EventType,
    TimeMode,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select, update

from cquptddl import core
from cquptddl.exc import _MeetscheduleBatchActionFailed
from cquptddl.model.db import Homework
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.db.meetschedule_tracked_event import (
    MeetscheduleEntry,
    MeetscheduleEntryStatus,
)

from . import limiter

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def _job():
    # 注意：client必须专人专用，不然就会串号
    async with core.get_session() as session:
        # 拿所有已跟踪的作业
        sql = select(MeetscheduleEntry)
        resp = await session.execute(sql)
        entries = resp.scalars().all()

        async with _log_and_suppress(info="推送时发生异常"):
            pending_entries = [
                e for e in entries if e.status == MeetscheduleEntryStatus.PENDING
            ]
            await _handle_pending_entries(session, pending_entries)
        async with _log_and_suppress(info="更新时发生异常"):
            pending_update_entries = [
                e for e in entries if e.status == MeetscheduleEntryStatus.PENDING_UPDATE
            ]
            await _handle_pending_update_entries(session, pending_update_entries)
        async with _log_and_suppress(info="删除时发生异常"):
            pending_delete_entries = [
                e for e in entries if e.status == MeetscheduleEntryStatus.PENDING_DELETE
            ]
            await _handle_pending_delete_entries(session, pending_delete_entries)
        async with _log_and_suppress(info="拉取时发生异常"):
            success_entries = [
                e for e in entries if e.status == MeetscheduleEntryStatus.SUCCESS
            ]
            await _handle_pull(session, success_entries)


async def _handle_pending_entries(
    session: AsyncSession, entries: Iterable[MeetscheduleEntry]
):
    # 拿作业
    homework_ids = {e.id for e in entries}
    sql = select(Homework).where(Homework.id.in_(homework_ids))  # ty: ignore[unresolved-attribute]
    resp = await session.execute(sql)
    homeworks = resp.scalars().all()

    # 按用户整理
    userid_homeworks_map = defaultdict[str, set[Homework]](set)
    for h in homeworks:
        userid_homeworks_map[h.user_id].add(h)

    # 处理每个用户
    failed_homework_ids = set[UUID]()
    pending_homework_ids = set[UUID]()
    for uid, hs in userid_homeworks_map.items():
        try:
            await _add_new_homeworks_for_user(session, uid, hs)
        except _MeetscheduleBatchActionFailed as e:
            failed_homework_ids |= e.failed_homework_ids
            pending_homework_ids |= e.pending_homework_ids
        except Exception as e:
            _logger.error("向用户%s的meet课程表推送作业时发生异常", exc_info=e)
            pending_homework_ids.update(h.id for h in hs)

    # 处理失败作业
    sql = delete(MeetscheduleEntry).where(MeetscheduleEntry.id.in_(failed_homework_ids))  # ty: ignore[unresolved-attribute]
    await session.execute(sql)

    # 处理成功作业
    success_homework_ids = homework_ids - failed_homework_ids - pending_homework_ids
    if success_homework_ids:
        sql = (
            update(MeetscheduleEntry)
            .where(MeetscheduleEntry.id.in_(success_homework_ids))  # ty: ignore[unresolved-attribute]
            .values(status=MeetscheduleEntryStatus.SUCCESS)
        )
        await session.execute(sql)


async def _add_new_homeworks_for_user(
    session: AsyncSession, user_id: str, homeworks: Iterable[Homework]
):
    """
    Raises:
        _MeetscheduleBatchActionFailed:
    ---
    bundle: [(homework_id, EventInput), ...]，所有作业
    batch: [(homework_id, EventInput), ...]，100个为一批的作业
    """
    # 拿配置
    c = await session.get_one(MeetscheduleConfig, user_id)

    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(c.api_key, client=client) as meet,
    ):
        # 拿课程
        async with limiter.acquire(meet):
            courses = await meet.courses.get_all(c.schedule_id)
        course_name_id_map = {c.name: c.id for c in courses}

        # 建bundle
        event_bundle = list[tuple[UUID, EventInput]]()
        for h in homeworks:
            if h.deadline is None:
                continue
            event_bundle.append(
                (
                    h.id,
                    EventInput(
                        schedule_id=c.schedule_id,
                        type=EventType.HOMEWORK,
                        title=h.title,
                        time_mode=TimeMode.DUE_ONLY,
                        end_at=h.deadline.isoformat(),
                        linked_course_id=course_name_id_map.get(h.course_name),
                        done=h.done,
                    ),
                )
            )

        # 发请求并记录失败作业id
        failed_homework_ids = set[UUID]()
        pending_homework_ids = set[UUID]()
        for batch in batched(event_bundle, 100):
            try:
                await _create_batch_events_with_fallback(meet, c.schedule_id, batch)
            except _MeetscheduleBatchActionFailed as e:
                failed_homework_ids |= e.failed_homework_ids
                pending_homework_ids |= e.pending_homework_ids

        # 处理失败的作业
        if failed_homework_ids or pending_homework_ids:
            raise _MeetscheduleBatchActionFailed(
                failed_homework_ids, pending_homework_ids
            )


async def _create_batch_events_with_fallback(
    meet: AsyncMeetSchedule, schedule_id: str, batch: Iterable[tuple[UUID, EventInput]]
):
    # 发请求
    async with limiter.acquire(meet):
        try:
            await meet.events.create_batch(schedule_id, [i[1] for i in batch])
        except (
            meetschedule_sdk.exceptions.UnprocessableEntityError,
            meetschedule_sdk.exceptions.ConflictError,
        ):
            await _create_batch_events_singly(meet, batch)


async def _create_batch_events_singly(
    meet: AsyncMeetSchedule, batch: Iterable[tuple[UUID, EventInput]]
):
    """
    Raises:
        _MeetscheduleBatchActionFailed:
    """
    failed_homework_ids = set[UUID]()
    pending_homework_ids = set[UUID]()
    for hid, e in batch:
        async with limiter.acquire(meet):
            try:
                await meet.events.create(e)
            except (
                meetschedule_sdk.exceptions.UnprocessableEntityError,
                meetschedule_sdk.exceptions.ConflictError,
            ) as e:
                _logger.warning(
                    "向meet课程表推送作业%s时发生失败性异常", hid, exc_info=e
                )
                failed_homework_ids.add(hid)
                continue
            except Exception as e:
                _logger.error("向meet课程表推送作业%s时发生未知异常", hid, exc_info=e)
                pending_homework_ids.add(hid)
    if failed_homework_ids or pending_homework_ids:
        raise _MeetscheduleBatchActionFailed(failed_homework_ids, pending_homework_ids)


async def _handle_pending_update_entries(
    session: AsyncSession, entries: Iterable[MeetscheduleEntry]
):
    # 拿作业
    homework_ids = {e.id for e in entries}
    sql = select(Homework).where(Homework.id.in_(homework_ids))  # ty: ignore[unresolved-attribute]
    resp = await session.execute(sql)
    homeworks = resp.scalars().all()
    id_homework_map = {h.id: h for h in homeworks}
    homework_eventid_bundle = {
        (e.meet_event_id, id_homework_map[e.id])
        for e in entries
        if e.meet_event_id is not None
    }

    # 按用户整理
    userid_homeworks_map = defaultdict[str, set[tuple[str, Homework]]](set)
    for eid, h in homework_eventid_bundle:
        assert eid
        userid_homeworks_map[h.user_id].add((eid, h))

    # 处理每个用户
    pending_update_homework_ids = set[UUID]()
    for uid, bundles in userid_homeworks_map.items():
        try:
            await _update_homeworks_for_user(session, uid, bundles)
        except _MeetscheduleBatchActionFailed as e:
            pending_update_homework_ids |= e.pending_homework_ids
        except Exception as e:
            _logger.error("向用户%s的meet课程表更新作业时发生异常", exc_info=e)
            pending_update_homework_ids.update(b[1].id for b in bundles)

    # 处理成功作业
    success_homework_ids = homework_ids - pending_update_homework_ids
    if success_homework_ids:
        sql = (
            update(MeetscheduleEntry)
            .where(MeetscheduleEntry.id.in_(success_homework_ids))  # ty: ignore[unresolved-attribute]
            .values(status=MeetscheduleEntryStatus.SUCCESS)
        )
        await session.execute(sql)


async def _update_homeworks_for_user(
    session: AsyncSession, user_id: str, bundles: Iterable[tuple[str, Homework]]
):
    """
    Raises:
        _MeetscheduleBatchActionFailed:
    """
    # 拿配置
    c = await session.get_one(MeetscheduleConfig, user_id)

    # 发请求
    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(c.api_key, client=client) as meet,
    ):
        pending_homework_ids = set[UUID]()
        for eid, h in bundles:
            async with limiter.acquire(meet):
                try:
                    await meet.events.update(eid, EventPatch(done=h.done))
                except Exception as e:
                    _logger.error(
                        "向meet课程表更新作业%s时发生未知异常", h.id, exc_info=e
                    )
                    pending_homework_ids.add(h.id)

    # 报失败
    if pending_homework_ids:
        raise _MeetscheduleBatchActionFailed(set(), pending_homework_ids)


async def _handle_pending_delete_entries(
    session: AsyncSession, entries: Iterable[MeetscheduleEntry]
):
    # 按用户整理
    userid_entry_map = defaultdict[str, list[MeetscheduleEntry]](list)
    for e in entries:
        userid_entry_map[e.user_id].append(e)

    # 处理每个用户
    pending_delete_homework_ids = set[UUID]()
    for uid, es in userid_entry_map.items():
        try:
            await _delete_homeworks_for_user(session, uid, es)
        except _MeetscheduleBatchActionFailed as e:
            pending_delete_homework_ids |= e.pending_homework_ids
        except Exception as e:
            _logger.error("向用户%s的meet课程表推送作业时发生异常", exc_info=e)
            pending_delete_homework_ids.update(entry.id for entry in es)

    # 处理成功作业
    success_homework_ids = {e.id for e in entries} - pending_delete_homework_ids
    if success_homework_ids:
        sql = delete(MeetscheduleEntry).where(
            MeetscheduleEntry.id.in_(success_homework_ids)  # ty: ignore[unresolved-attribute]
        )
        await session.execute(sql)


async def _delete_homeworks_for_user(
    session: AsyncSession, user_id: str, es: Iterable[MeetscheduleEntry]
):
    """
    Raises:
        _MeetscheduleBatchActionFailed:
    """
    # 拿配置
    c = await session.get_one(MeetscheduleConfig, user_id)
    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(c.api_key, client=client) as meet,
    ):
        pending_delete_homework_ids = set[UUID]()
        for batch in batched(es, 100):
            try:
                await _delete_batch_events(meet, batch)
            except _MeetscheduleBatchActionFailed:
                pending_delete_homework_ids.update(e.id for e in batch)

    if pending_delete_homework_ids:
        raise _MeetscheduleBatchActionFailed(set(), pending_delete_homework_ids)


async def _delete_batch_events(
    meet: AsyncMeetSchedule, batch: Iterable[MeetscheduleEntry]
):
    if not (ids := [e.meet_event_id for e in batch if e.meet_event_id]):
        return
    async with limiter.acquire(meet):
        try:
            await meet.events.delete_batch(ids)
        except Exception as e:
            _logger.error("向meet课程表删除作业%s时发生未知异常", exc_info=e)
            raise _MeetscheduleBatchActionFailed(set(), set())


async def _handle_pull(session: AsyncSession, entries: Iterable[MeetscheduleEntry]):
    # 拿作业
    homework_ids = {i.id for i in entries}
    sql = select(Homework).where(Homework.id.in_(homework_ids))  # ty: ignore[unresolved-attribute]
    resp = await session.execute(sql)
    homeworks = resp.scalars().all()
    id_homework_map = {h.id: h for h in homeworks}

    # 按用户整理
    userid_eventid_homework_map = defaultdict[str, set[tuple[str, Homework]]](set)
    for e in entries:
        assert e.meet_event_id
        userid_eventid_homework_map[e.user_id].add(
            (e.meet_event_id, id_homework_map[e.id])
        )

    # 对所有用户拉取
    pending_homework_ids = set[UUID]()
    for uid, bundle in userid_eventid_homework_map.items():
        try:
            await _pull_homeworks_for_user(session, uid, bundle)
        except _MeetscheduleBatchActionFailed as e:
            pending_homework_ids |= e.pending_homework_ids

    # 处理pending的作业
    sql = (
        update(MeetscheduleEntry)
        .where(MeetscheduleEntry.id.in_(pending_homework_ids))  # ty: ignore[unresolved-attribute]
        .values(status=MeetscheduleEntryStatus.PENDING)
    )
    await session.execute(sql)


async def _pull_homeworks_for_user(
    session: AsyncSession, user_id: str, bundle: Iterable[tuple[str, Homework]]
):
    c = await session.get_one(MeetscheduleConfig, user_id)
    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(c.api_key, client=client) as meet,
    ):
        pending_homework_ids = set[UUID]()
        for batch in batched(bundle, 100):
            try:
                await _pull_batch(meet, batch)
            except _MeetscheduleBatchActionFailed as e:
                pending_homework_ids |= e.pending_homework_ids
            except Exception as e:
                _logger.error("批量同步用户%s的作业时发生异常", user_id, exc_info=e)

    if pending_homework_ids:
        raise _MeetscheduleBatchActionFailed(set(), pending_homework_ids)


async def _pull_batch(meet: AsyncMeetSchedule, batch: Iterable[tuple[str, Homework]]):
    # 拉
    async with limiter.acquire(meet):
        events = await meet.events.get_by_ids([i[0] for i in batch])
    id_event_map = {e.id: e for e in events}

    # 同步
    pending_homework_ids = set[UUID]()
    for event_id, h in dict(batch).items():
        event = id_event_map.get(event_id)
        if event is None:
            _logger.warning("拉取meet作业时未发现作业%s的远端记录", h.id)
            pending_homework_ids.add(h.id)
            continue

        if event.done != h.done:
            h.done = event.done

    if pending_homework_ids:
        raise _MeetscheduleBatchActionFailed(set(), pending_homework_ids)


@asynccontextmanager
async def _log_and_suppress(
    exc: type[BaseException] = Exception, info: str = "发生异常", *info_args
):
    try:
        yield
    except exc as e:
        _logger.error(info, *info_args, exc_info=e)


scheduler = AsyncIOScheduler()
scheduler.add_job(
    _job,
    IntervalTrigger(seconds=core.config.meetschedule_sync_interval),
)


def start_refresh():
    scheduler.start()


def shutdown_refresh():
    scheduler.shutdown()
