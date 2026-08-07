from contextlib import asynccontextmanager

from fastapi import FastAPI

from cquptddl import core
from cquptddl.router import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await core.db._migrate_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)


def main():
    import uvicorn

    uvicorn.run(app, host=None)  # ty: ignore[invalid-argument-type]
