import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cquptddl import core
from cquptddl.core import config
from cquptddl.router import router

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.getLogger(
        "cquptddl.service.homework.platform.chaoxing:unknown-inbox"
    ).disabled = not core.config.DEBUG
    await core.db._migrate_db()
    core.task.start()
    logger.info("服务已就绪")
    yield
    logger.info("开始清理")
    try:
        await asyncio.wait_for(core.task.shutdown(), timeout=10)
    except TimeoutError as e:
        logger.error("任务停止超时", exc_info=e)


app = FastAPI(lifespan=lifespan)
app.include_router(router)


def main():
    import uvicorn

    uvicorn.run(
        "cquptddl:app",
        host="127.0.0.1" if config.DEBUG else None,  # ty: ignore[invalid-argument-type]
        reload=config.DEBUG,
    )
