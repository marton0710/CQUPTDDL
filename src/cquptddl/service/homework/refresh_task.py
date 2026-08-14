from logging import INFO, getLogger

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import select

from cquptddl import core
from cquptddl.model.db import PlatformInfo, User
from cquptddl.model.event import (
    AutoRefreshHomeworkFailedEvent,
    PlatformBoundEvent,
    PlatformUnboundEvent,
)
from cquptddl.model.schema.platform_auth import PlatformEnum

from .refresh_homework import refresh_homework

scheduler = AsyncIOScheduler()
_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def init_refresh_task():
    async with core.factory.get_session() as session:
        stmt = select(PlatformInfo)
        resp = await session.execute(stmt)
        items = resp.scalars().all()
        for i in items:
            add_job(i.user_id, i.platform)
        _logger.info("后台刷新任务初始化完成，共添加%s个任务", len(items))


def _generate_job_id(uid: str, platform_name: str) -> str:
    return f"homework_fetch_schedule_{uid}_{platform_name}"


def add_job(uid: str, platform_name: PlatformEnum):
    job = scheduler.add_job(
        _job,
        "interval",
        args=(uid, platform_name),
        id=_generate_job_id(uid, platform_name),
        seconds=core.config.homework_cache_base_ttl,
        jitter=core.config.homework_cache_jitter,
        replace_existing=True,
    )
    _logger.debug("添加任务：用户%s，平台%s，任务%s", uid, platform_name, job)


def del_job(uid: str, platform_name: PlatformEnum):
    _logger.debug("删除任务：用户%s，平台%s", uid, platform_name)
    try:
        scheduler.remove_job(_generate_job_id(uid, platform_name))
    except JobLookupError as e:
        _logger.warning(
            "移除任务时未找到：用户：%s，平台：%s", uid, platform_name, exc_info=e
        )


async def _job(uid: str, platform_name: PlatformEnum):
    try:
        async with core.get_session() as session:
            user = await session.get(User, uid)
            assert user is not None
            await refresh_homework(session, user, platform_name)
            _logger.info("用户%s在平台%s的作业自动刷新成功", uid, platform_name)
    except Exception as e:
        _logger.error(
            "用户%s自动刷新平台%s时发生异常：", uid, platform_name, exc_info=e
        )
        core.bus.emit(
            AutoRefreshHomeworkFailedEvent(uid=uid, platform_name=platform_name, exc=e)
        )


core.bus.on(PlatformBoundEvent, lambda e: add_job(e.uid, e.platform_name))
core.bus.on(PlatformUnboundEvent, lambda e: del_job(e.uid, e.platform_name))
