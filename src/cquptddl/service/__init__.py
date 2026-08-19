import logging

from cquptddl import core

from . import auth, crypto, homework, meetschedule, platform, qqpush  # noqa: F401


async def init():
    logging.getLogger(
        "cquptddl.service.platform.chaoxing:unknown-inbox"
    ).disabled = not core.config.DEBUG
    homework.refresh_task.scheduler.start()
    await homework.refresh_task.init_refresh_task()


async def shutdown():
    homework.refresh_task.scheduler.shutdown()
