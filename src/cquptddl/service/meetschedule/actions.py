from collections.abc import Iterable
from datetime import datetime
from logging import INFO, getLogger

from meetschedule_sdk import (
    AsyncMeetSchedule,
    EventInput,
    EventPatch,
    EventType,
    TimeMode,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from cquptddl import core
from cquptddl.exc import MeetscheduleNotBound
from cquptddl.model.db import Homework
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.db.meetschedule_tracked_event import MeetscheduleTrackedEvent
from cquptddl.model.event import HomeworkDoneEvent, HomeworkRefreshedEvent

from . import limiter

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def delete_events(session: AsyncSession, user_id: str):
    config = await session.get_one(MeetscheduleConfig, user_id)
    sql = select(MeetscheduleTrackedEvent.id).where(
        MeetscheduleTrackedEvent.user_id == user_id
    )
    resp = await session.execute(sql)
    event_ids = resp.scalars().all()

    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(config.meetschedule_key, client=client) as meet,
    ):
        for i in event_ids:
            async with limiter.acquire(meet):
                await meet.events.delete(i)

    sql = delete(MeetscheduleTrackedEvent).where(
        MeetscheduleTrackedEvent.user_id == user_id  # ty: ignore[invalid-argument-type]
    )
    await session.execute(sql)


async def add_new_homeworks(
    session: AsyncSession, config: MeetscheduleConfig, homeworks: Iterable[Homework]
):
    async with (
        core.get_client() as client,
        AsyncMeetSchedule(config.meetschedule_key, client=client) as meet,
    ):
        # 尝试获取同名课程
        async with limiter.acquire(meet):
            courses = await meet.courses.get_all(config.schedule_id)
        course_name_id_map = {c.name: c.id for c in courses}

        # 添加作业
        for h in homeworks:
            # 发送请求
            async with limiter.acquire(meet):
                event = await meet.events.create(
                    EventInput(
                        schedule_id=config.schedule_id,
                        type=EventType.HOMEWORK,
                        title=h.title,
                        time_mode=TimeMode.DUE_ONLY,
                        end_at=None if h.deadline is None else h.deadline.isoformat(),
                        linked_course_id=course_name_id_map.get(h.course_name),
                        done=h.done,
                    ),
                    allow_duplicate_title=True,
                )

            # 落库
            session.add(
                MeetscheduleTrackedEvent(
                    id=event.id,
                    user_id=config.user_id,
                    homework_id=h.id,
                )
            )


async def complete_homework(
    session: AsyncSession, config: MeetscheduleConfig, homework: Homework
):
    sql = select(MeetscheduleTrackedEvent).where(
        MeetscheduleTrackedEvent.homework_id == homework.id
    )
    resp = await session.execute(sql)
    meet_homework = resp.scalar_one_or_none()
    if meet_homework is None:
        _logger.error(
            "向meet课程表推送作业%s完成状态时，发现无对应的跟踪作业", homework.id
        )
        return

    async with (
        core.factory.get_client() as client,
        AsyncMeetSchedule(config.meetschedule_key, client=client) as meet,
        limiter.acquire(meet),
    ):
        await meet.events.update(meet_homework.id, EventPatch(done=homework.done))

    meet_homework.updated_at = datetime.now()  # noqa: DTZ005


async def sync_done_status_for_all_tracked_homeworks():
    # 注意：client必须专人专用，不然就会串号
    async with core.get_session() as session:
        # 拿到所有绑定了meet课程表的人
        sql = select(MeetscheduleConfig)
        resp = await session.execute(sql)
        configs = resp.scalars().all()

        # 拿到跟踪的所有作业事件记录
        sql = select(MeetscheduleTrackedEvent)
        resp = await session.execute(sql)
        all_tracked_homework_entries = resp.scalars().all()
        all_tracked_homework_entries_map = {
            e.id: e for e in all_tracked_homework_entries
        }

        # 拿到跟踪的作业本体
        sql = select(Homework).where(
            Homework.id.in_([i.homework_id for i in all_tracked_homework_entries])  # ty: ignore[unresolved-attribute]
        )
        resp = await session.execute(sql)
        all_tracked_homeworks = resp.scalars().all()
        all_tracked_homeworks_map = {h.id: h for h in all_tracked_homeworks}

        # 对于每个用户
        for c in configs:
            # 拿到当前用户的作业事件记录id列表
            user_homework_event_ids = [
                i.id for i in all_tracked_homework_entries if i.user_id == c.user_id
            ]

            # 用作业id列表拿云端数据集
            try:
                async with (
                    core.factory.get_client() as client,
                    AsyncMeetSchedule(c.meetschedule_key, client=client) as meet,
                    limiter.acquire(meet),
                ):
                    cloud_homework_events = await meet.events.get_by_ids(
                        user_homework_event_ids
                    )
                cloud_homework_events_map = {e.id: e for e in cloud_homework_events}
            except Exception as e:
                _logger.error("用户%s的meet课程表对账失败", c.user_id, exc_info=e)
                continue

            # 对账
            for i in user_homework_event_ids:
                local_entry = all_tracked_homework_entries_map[i]
                local_homework = all_tracked_homeworks_map[local_entry.homework_id]
                remote_event = cloud_homework_events_map.get(i)
                if remote_event is None:  # 如果用户在meet删除了作业
                    await add_new_homeworks(session, c, [local_homework])
                    continue
                if local_homework.done != remote_event.done:
                    local_homework.done = remote_event.done
                    local_entry.updated_at = datetime.now()  # noqa: DTZ005


async def _on_recv_new_homework(event: HomeworkRefreshedEvent):
    _logger.debug("收到作业刷新事件")
    if not event.new_homework_ids:
        _logger.debug("没有发现新作业")
        return

    async with core.factory.get_session() as session:
        # 查config
        config = await session.get(MeetscheduleConfig, event.uid)
        if config is None:
            return

        # 查作业
        sql = select(Homework).where(Homework.id.in_(event.new_homework_ids))  # ty: ignore[unresolved-attribute]
        resp = await session.execute(sql)
        new_homeworks = resp.scalars().all()
        _logger.debug("发现新作业：%s", [i.title for i in new_homeworks])

        # 执行操作
        try:
            await add_new_homeworks(session, config, new_homeworks)
        except MeetscheduleNotBound:
            return


async def _on_recv_homework_done_event(event: HomeworkDoneEvent):
    async with core.factory.get_session() as session:
        h = await session.get_one(Homework, event.homework_id)
        c = await session.get(MeetscheduleConfig, h.user_id)
        if c is None:
            return
        await complete_homework(session, c, h)


core.bus.on(HomeworkRefreshedEvent, _on_recv_new_homework)
core.bus.on(HomeworkDoneEvent, _on_recv_homework_done_event)
