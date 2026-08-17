from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib import metadata

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .db import _session_maker

HEADERS = {"User-Agent": f"CQUPTDDL/{metadata.version('cquptddl')}"}


async def depends_client(**kw) -> AsyncGenerator[AsyncClient]:
    if "headers" in kw:
        kw["headers"] = HEADERS | kw["headers"]
    else:
        kw["headers"] = HEADERS.copy()
    async with AsyncClient(**kw) as client:
        yield client


async def depends_session() -> AsyncGenerator[AsyncSession]:
    async with _session_maker() as session:
        yield session
        await session.commit()


get_session = asynccontextmanager(depends_session)
get_client = asynccontextmanager(depends_client)
