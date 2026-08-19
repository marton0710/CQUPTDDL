import asyncio
from collections.abc import Iterable
from logging import getLogger

from httpx import URL

from cquptddl import core
from cquptddl.model.db import Homework
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import InvalidQQChanIDEvent

_logger = getLogger(__name__)
buffer: dict[str, list[Homework]] = {}
_buffer_lock = asyncio.Lock()

DYING_HOMEWORK_TEMPLATE = """# 临期作业提醒
{homeworks}"""
SINGLE_HOMEWORK_TEMPLATE = """## [{title}]({url})
- 课程：{course}
- 平台：{platform}
- 截止时间：{deadline}"""


async def push_dying_homework(homework: Homework):
    async with _buffer_lock:
        buffer.setdefault(homework.user_id, []).append(homework)


async def push_dying_homeworks(user_id: str, homeworks: Iterable[Homework]):
    async with core.factory.get_session() as session:
        c = await session.get(QQPushConfig, user_id)
        assert c
        if c.qqchan_id is None:
            _logger.warning("用户%s没有配置qqchan_id却触发了推送", user_id)
            return

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
    async with core.get_client() as client:
        try:
            resp = await client.post(
                URL(core.config.QQBOT_URL).join("/qqchan/send"),
                content=msg,
                params={"id": c.qqchan_id, "ismarkdown": True},
                headers={"X-API-Key": core.config.QQBOT_RECV_API_KEY},
            )
        except Exception as e:
            _logger.error("推送异常", exc_info=e)
        data: dict[str, bool | str] = resp.json()
        if data["success"]:
            return
        if data["msg"] == "无此id":
            core.bus.emit(InvalidQQChanIDEvent(uid=user_id))
            _logger.warning("用户%s的qqchan_id是非法的", user_id)
        else:
            _logger.error("推送失败：%s", data["msg"])


async def push_buffered_homeworks():
    async with _buffer_lock:
        if not buffer:
            return
        for user_id, homeworks in buffer.items():
            await push_dying_homeworks(user_id, homeworks)
        buffer.clear()
