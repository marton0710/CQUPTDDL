import logging

from cquptddl import core

from . import auth, crypto, homework, platform  # noqa: F401


async def init():
    logging.getLogger(
        "cquptddl.service.platform.chaoxing:unknown-inbox"
    ).disabled = not core.config.DEBUG


async def shutdown():
    pass
