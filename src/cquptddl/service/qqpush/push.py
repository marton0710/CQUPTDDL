import asyncio
from collections.abc import Iterable
from logging import getLogger

from cquptddl.model.db import Homework

_logger = getLogger(__name__)
buffer: dict[str, list[Homework]] = {}
_buffer_lock = asyncio.Lock()


async def push_dying_homework(homework: Homework):
    async with _buffer_lock:
        buffer.setdefault(homework.user_id, []).append(homework)


async def push_dying_homeworks(user_id: str, homeworks: Iterable[Homework]):
    _logger.info("模拟推送：用户%s", user_id)
    for h in homeworks:
        _logger.info("\t作业：%s", h.model_dump())


async def push_buffered_homeworks():
    async with _buffer_lock:
        if not buffer:
            return
        for user_id, homeworks in buffer.items():
            await push_dying_homeworks(user_id, homeworks)
        buffer.clear()
