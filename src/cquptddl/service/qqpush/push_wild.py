import asyncio
from collections.abc import Iterable
from logging import getLogger
from uuid import UUID

from httpx import URL
from sqlmodel import select

from cquptddl import core
from cquptddl.model.db import Homework
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import (
    AutoRefreshHomeworkFailedEvent,
    HomeworkRefreshedEvent,
    InvalidQQChanIDEvent,
    UserReloginRequiredEvent,
)
from cquptddl.model.schema.platform import PlatformEnum

_logger = getLogger(__name__)
buffer: dict[str, list[Homework]] = {}
_buffer_lock = asyncio.Lock()

DYING_HOMEWORK_TEMPLATE = """【临期作业提醒】
{homeworks}"""
NEW_HOMEWORK_TEMPLATE = """【新作业提醒】
{homeworks}"""
SINGLE_HOMEWORK_TEMPLATE = """{title}
- 课程：{course}
- 平台：{platform}
- 截止时间：{deadline}
- 传送门：{url}
"""
HOMEWORK_ALL_DONE_TEMPLATE = "未发现{scope}小时内截止的作业"
REFRESH_HOMEWORK_FAILED_NOTICE_TEMPLATE = (
    "系统自动刷新{platform_name}平台作业时失败。请检查绑定状态，或联系管理员"
)
RELOGIN_REQUIRED_NOTICE_TEMPLATE = "你的聚合截止线登录已过期，请重新登录"


async def push_dying_homework(homework: Homework):
    async with _buffer_lock:
        buffer.setdefault(homework.user_id, []).append(homework)


async def push_dying_homeworks(user_id: str, homeworks: Iterable[Homework]):
    c = await _get_user_qqpush_config(user_id)
    if not homeworks:
        msg = HOMEWORK_ALL_DONE_TEMPLATE.format(scope=c.qq_push_scope)
    else:
        homework_msgs: list[str] = []
        for h in homeworks:
            homework_msgs.append(
                SINGLE_HOMEWORK_TEMPLATE.format(
                    title=h.title,
                    url=h.url,
                    course=h.course_name,
                    platform=h.platform,
                    deadline=h.deadline,
                )
            )
        msg = DYING_HOMEWORK_TEMPLATE.format(homeworks="\n".join(homework_msgs))
    await _push(c, msg, True)


async def push_new_homeworks(user_id: str, homework_ids: Iterable[UUID]):
    if not homework_ids:
        return

    async with core.factory.get_session() as session:
        sql = select(Homework).where(Homework.id.in_(homework_ids))  # ty: ignore[unresolved-attribute]
        resp = await session.execute(sql)
        homeworks = resp.scalars().all()

    c = await _get_user_qqpush_config(user_id)
    homework_msgs = list[str]()
    for h in homeworks:
        homework_msgs.append(
            SINGLE_HOMEWORK_TEMPLATE.format(
                title=h.title,
                url=h.url,
                course=h.course_name,
                platform=h.platform,
                deadline=h.deadline,
            )
        )
    msg = NEW_HOMEWORK_TEMPLATE.format(homeworks="\n".join(homework_msgs))
    await _push(c, msg, True)


async def push_buffered_homeworks():
    async with _buffer_lock:
        if not buffer:
            return
        for user_id, homeworks in buffer.items():
            try:
                await push_dying_homeworks(user_id, homeworks)
            except Exception as e:
                _logger.error(
                    "批量推送已缓冲的实时用户%s作业时发生异常", user_id, exc_info=e
                )
        buffer.clear()


async def push_refresh_homework_failed_notice(
    user_id: str, platform_name: PlatformEnum
):
    await _push(
        await _get_user_qqpush_config(user_id),
        REFRESH_HOMEWORK_FAILED_NOTICE_TEMPLATE.format(platform_name=platform_name),
    )


async def push_relogin_required_msg(user_id: str):
    config = await _get_user_qqpush_config(user_id)
    await _push(config, RELOGIN_REQUIRED_NOTICE_TEMPLATE)


async def _get_user_qqpush_config(user_id: str) -> QQPushConfig:
    async with core.factory.get_session() as session:
        return await session.get_one(QQPushConfig, user_id)


async def _push(qqpush_config: QQPushConfig, msg: str, ismarkdown: bool = False):
    if qqpush_config.qqchan_id is None:
        _logger.debug("用户%s没有配置qq推送", qqpush_config.user_id)
        return

    async with core.factory.get_client() as client:
        try:
            resp = await client.post(
                URL(core.config.QQBOT_URL).join("/qqchan/send"),
                content=msg,
                params={"id": qqpush_config.qqchan_id},
                headers={"X-API-Key": core.config.QQBOT_RECV_API_KEY},
            )
        except Exception as e:
            _logger.error("推送异常", exc_info=e)
            return
        data: dict[str, bool | str] = resp.json()
        if data["success"]:
            return
        if data["msg"] == "无此id":
            core.bus.emit(InvalidQQChanIDEvent(uid=qqpush_config.user_id))
            _logger.warning("用户%s的qqchan_id是非法的", qqpush_config.user_id)
        else:
            _logger.error("用户%s推送失败：%s", qqpush_config.user_id, data["msg"])


core.bus.on(
    AutoRefreshHomeworkFailedEvent,
    lambda e: push_refresh_homework_failed_notice(e.uid, e.platform_name),
)
core.bus.on(UserReloginRequiredEvent, lambda e: push_relogin_required_msg(e.uid))
core.bus.on(
    HomeworkRefreshedEvent, lambda e: push_new_homeworks(e.uid, e.new_homework_ids)
)
