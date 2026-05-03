# import asyncio
from fastapi import FastAPI
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
