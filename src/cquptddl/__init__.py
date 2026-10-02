import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cquptddl import core, router, service

logging.basicConfig(level=logging.WARNING)
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await core.init()
    await service.init()
    _logger.info("服务已就绪")
    yield
    _logger.info("开始清理")
    await service.shutdown()
    await core.shutdown()


app = FastAPI(lifespan=lifespan)
app.include_router(router.router)


def main():
    import uvicorn

    uvicorn.run(
        "cquptddl:app",
        host="127.0.0.1" if core.config.DEBUG else None,  # ty: ignore[invalid-argument-type]
        reload=core.config.DEBUG,
    )
