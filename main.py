# import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import router
from app.db.init import init_db

# if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
#     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy()) # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """首次启动"""
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router=router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境用）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法：GET, POST, PUT, DELETE, OPTIONS...
    allow_headers=["*"],  # 允许所有请求头
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
