import asyncio
from logging import INFO, getLogger

from . import db, task
from .config import config
from .event_bus import bus
from .factory import depends_client, depends_session, get_client, get_session
from .symbol import call, export

__all__ = [
    "bus",
    "call",
    "config",
    "depends_client",
    "depends_session",
    "export",
    "factory",
    "get_client",
    "get_session",
    "task",
]

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def init():
    await db._migrate_db()
    task.start()


async def shutdown():
    try:
        await asyncio.wait_for(task.shutdown(), timeout=10)
    except TimeoutError as e:
        _logger.error("任务停止超时", exc_info=e)
