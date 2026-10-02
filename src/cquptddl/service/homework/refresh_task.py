from logging import INFO, getLogger

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import select

from cquptddl import core
from cquptddl.exc import CquptddlException, RefreshCoolingDown
from cquptddl.model.db import PlatformInfo, User
from cquptddl.model.event import (
    AutoRefreshHomeworkFailedEvent,
)
from cquptddl.model.schema.platform import PlatformEnum

from .refresh_homework import refresh_homework

scheduler = AsyncIOScheduler()
_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def init_refresh_task():
    scheduler.start()
    async with core.factory.get_session() as session:
        stmt = select(PlatformInfo)
        resp = await session.execute(stmt)
        items = resp.scalars().all()
        for i in items:
            await add_job(i.user_id, i.platform)
        _logger.info("后台刷新任务初始化完成，共添加%s个任务", len(items))


def _generate_job_id(uid: str, platform_name: str) -> str:
    return f"homework_fetch_schedule_{uid}_{platform_name}"


@core.hook.on("platform.after_bind", background=True)
async def add_job(user_id: str, platform_name: PlatformEnum):
    job = scheduler.add_job(
        _job,
        "interval",
        args=(user_id, platform_name),
        id=_generate_job_id(user_id, platform_name),
        seconds=core.config.homework_cache_base_ttl,
        jitter=core.config.homework_cache_jitter,
        replace_existing=True,
    )
    _logger.debug("添加任务：用户%s，平台%s，任务%s", user_id, platform_name, job)


@core.hook.on("platform.after_unbind", background=True)
async def del_job(user_id: str, platform_name: PlatformEnum):
    _logger.debug("删除任务：用户%s，平台%s", user_id, platform_name)
    try:
        scheduler.remove_job(_generate_job_id(user_id, platform_name))
    except JobLookupError as e:
        _logger.warning(
            "移除任务时未找到：用户：%s，平台：%s", user_id, platform_name, exc_info=e
        )


async def _job(uid: str, platform_name: PlatformEnum):
    try:
        async with core.factory.get_session() as session:
            user = await session.get_one(User, uid)
            await refresh_homework(session, user, platform_name)
            _logger.debug("用户%s在平台%s的作业自动刷新成功", uid, platform_name)
    except RefreshCoolingDown:
        _logger.warning("用户%s自动刷新平台%s时还在冷却中", uid, platform_name)
    except Exception as e:
        if isinstance(e, CquptddlException):
            _logger.error(
                "用户%s自动刷新平台%s时发生异常：%s: %s", uid, platform_name, type(e), e
            )
        else:
            _logger.error(
                "用户%s自动刷新平台%s时发生异常：", uid, platform_name, exc_info=e
            )
        core.bus.emit(
            AutoRefreshHomeworkFailedEvent(uid=uid, platform_name=platform_name, exc=e)
        )


@core.hook.on("auth.after_delete_user", background=True)
async def _on_delete_user(user_id: str):
    for platform in PlatformEnum:
        try:
            scheduler.remove_job(_generate_job_id(user_id, platform))
        except JobLookupError:
            pass
